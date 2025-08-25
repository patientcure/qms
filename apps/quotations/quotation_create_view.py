from django.http import JsonResponse
from django.db import transaction
from django.conf import settings
import json
import logging
from .models import Product, TermsAndConditions, ActivityLog
from .forms import QuotationForm, QuotationItemFormSet
from .choices import ActivityAction
from .utils import send_and_archive_quotation
from .save_quotation import save_quotation_pdf
from .views import BaseAPIView
from .forms import CustomerForm
from .models import Customer
logger = logging.getLogger(__name__)
from apps.accounts.models import User, Roles
from django.db.models import Count

class QuotationCreateView(BaseAPIView):
    @transaction.atomic
    def post(self, request):
            try:
                request_json = getattr(request, 'json', {})
                if not request_json:
                    return JsonResponse({
                        'success': False,
                        'error': 'JSON data is required'
                    }, status=400)

                form_data = {**request.POST.dict(), **request_json}

                # --- Customer Handling ---
                customer_data = form_data.get('customer', {})
                if not isinstance(customer_data, dict):
                    customer_data = {}
                phone = customer_data.get('phone')
                if not phone:
                    return JsonResponse({
                        'success': False,
                        'error': 'Customer phone is required'
                    }, status=400)


                customer = Customer.objects.filter(phone=phone).first()
                if customer:
                    customer_id = customer.id
                else:
                    customer_form = CustomerForm(customer_data)
                    if not customer_form.is_valid():
                        return JsonResponse({
                            'success': False,
                            'error': 'Invalid customer data',
                            'customer_errors': customer_form.errors
                        }, status=400)
                    customer = customer_form.save()
                    customer_id = customer.id

                # --- Quotation Handling ---
                quotation_data = {k: v for k, v in form_data.items() 
                                  if k not in ['items', 'terms', 'send_immediately', 'auto_assign', 'customer']}
                quotation_data['customer'] = customer_id

                required_fields = ['customer', 'status']
                missing_fields = [field for field in required_fields 
                                  if field not in quotation_data or not quotation_data[field]]
                if missing_fields:
                    return JsonResponse({
                        'success': False,
                        'error': f'Missing required fields: {missing_fields}'
                    }, status=400)

                items_data = request_json.get('items', [])
                if not items_data:
                    return JsonResponse({
                        'success': False,
                        'error': 'At least one item is required'
                    }, status=400)

                for i, item in enumerate(items_data):
                    if 'product' not in item:
                        return JsonResponse({
                            'success': False,
                            'error': f'Item {i} missing product field'
                        }, status=400)
                    if 'quantity' not in item:
                        return JsonResponse({
                            'success': False,
                            'error': f'Item {i} missing quantity field'
                        }, status=400)

                terms_data = request_json.get('terms', [])
                valid_term_ids = self._validate_terms(terms_data)

                formset_data = self._prepare_formset_data(items_data)
                all_data = {**quotation_data, **formset_data}

                send_immediately = request_json.get('send_immediately', False)
                auto_assign = request_json.get('auto_assign', True)

                form = QuotationForm(quotation_data)
                formset = QuotationItemFormSet(all_data, prefix='items')

                if not (form.is_valid() and formset.is_valid()):
                    return self._handle_validation_errors(form, formset)

                quotation = form.save(commit=False)

                if not quotation.assigned_to and auto_assign:
                    salesperson = (
                        User.objects.filter(role=Roles.SALESPERSON, is_active=True)
                        .annotate(num_quotations=Count('quotations'))
                        .order_by('num_quotations', 'id')
                        .first()
                    )
                    if salesperson:
                        quotation.assigned_to = salesperson

                quotation.save()

                formset.instance = quotation
                formset.save()

                try:
                    quotation.recalculate_totals()
                except Exception as e:
                    logger.error(f"Failed to recalculate quotation totals: {str(e)}")

                if hasattr(request, 'user') and request.user.is_authenticated:
                    ActivityLog.log(
                        actor=request.user,
                        action=ActivityAction.QUOTATION_CREATED,
                        entity=quotation,
                        message="Created via API"
                    )

                pdf_url = None
                try:
                    pdf_path, pdf_url = save_quotation_pdf(quotation, request, terms=valid_term_ids)
                    quotation.file_url = pdf_url
                    quotation.save(update_fields=['file_url'])
                except Exception as e:
                    logger.error(f"PDF generation failed: {str(e)}")

                if send_immediately:
                    send_and_archive_quotation(quotation)
                    quotation.refresh_from_db()

                quotation_data = self._get_quotation_response_data(quotation, valid_term_ids)
                quotation_data['pdf_url'] = pdf_url

                return JsonResponse({
                    'success': True,
                    'message': f"Quotation {quotation.quotation_number} created successfully",
                    'data': quotation_data
                }, status=201)

            except Exception as e:
                logger.error(f"Error in QuotationCreateView: {str(e)}", exc_info=True)

                error_response = {
                    'success': False,
                    'error': f"Internal server error: {str(e)}"
                }

                if settings.DEBUG:
                    import traceback
                    error_response['debug_info'] = traceback.format_exc()

                return JsonResponse(error_response, status=500)
    
    def _validate_terms(self, terms_data):
        if not terms_data:
            return []
        
        try:
            if isinstance(terms_data, str):
                term_ids = [int(x.strip()) for x in terms_data.split(',') if x.strip()]
            elif isinstance(terms_data, list):
                term_ids = [int(x) for x in terms_data if str(x).strip()]
            else:
                return []
            
            valid_ids = list(TermsAndConditions.objects.filter(
                id__in=term_ids
            ).values_list('id', flat=True))
            
            return valid_ids
            
        except (ValueError, TypeError):
            return []
    
    def _prepare_formset_data(self, items_data):
        prefix = 'items'
        formset_data = {
            f'{prefix}-TOTAL_FORMS': str(len(items_data)),
            f'{prefix}-INITIAL_FORMS': '0',
            f'{prefix}-MIN_NUM_FORMS': '0',
            f'{prefix}-MAX_NUM_FORMS': '1000',
        }
        
        for i, item in enumerate(items_data):
            product = None
            product_id = item.get('product')
            if product_id:
                try:
                    product = Product.objects.get(id=product_id)
                except Product.DoesNotExist:
                    pass
            
            unit_price = item.get('unit_price')
            if not unit_price and product:
                unit_price = str(product.selling_price or '0.00')
            
            tax_rate = item.get('tax_rate')
            if not tax_rate and product:
                tax_rate = str(product.tax_rate or '0.00')
            
            description = item.get('description', '')
            if not description and product:
                description = product.name
            
            formset_data.update({
                f'{prefix}-{i}-product': product_id,
                f'{prefix}-{i}-description': description,
                f'{prefix}-{i}-quantity': item.get('quantity', 1),
                f'{prefix}-{i}-unit_price': unit_price,
                f'{prefix}-{i}-tax_rate': tax_rate,
            })
        
        return formset_data
    
    def _handle_validation_errors(self, form, formset):
        errors = {}
        
        if form.errors:
            errors['form'] = form.errors
        
        if formset.errors:
            errors['formset'] = formset.errors
        
        if hasattr(formset, 'non_form_errors') and formset.non_form_errors():
            errors['formset_non_form_errors'] = formset.non_form_errors()
        
        return JsonResponse({'success': False, 'errors': errors}, status=400)
    
    def _get_quotation_response_data(self, quotation, term_ids=None):
        try:
            items = []
            for item in quotation.items.select_related('product').all():
                item_data = {
                    'id': item.id,
                    'product': {
                        'id': item.product.id if item.product else None,
                        'name': item.product.name if item.product else None
                    },
                    'description': item.description,
                    'quantity': item.quantity,
                    'unit_price': float(item.unit_price),
                    'tax_rate': float(item.tax_rate),
                    'line_total': float(item.quantity * item.unit_price),
                    'line_tax': float(item.quantity * item.unit_price * item.tax_rate / 100),
                    'line_total_with_tax': float(item.quantity * item.unit_price * (1 + item.tax_rate / 100))
                }
                items.append(item_data)
            
            response_data = {
                'id': quotation.id,
                'quotation_number': quotation.quotation_number,
                'status': quotation.status,
                'subtotal': float(quotation.subtotal),
                'tax_total': float(quotation.tax_total),
                'total': float(quotation.total),
                'currency': quotation.currency,
                'customer': {
                    'id': quotation.customer.id,
                    'name': quotation.customer.name,
                    'email': quotation.customer.email
                },
                'assigned_to': {
                    'id': quotation.assigned_to.id if quotation.assigned_to else None,
                    'name': quotation.assigned_to.get_full_name() if quotation.assigned_to else None
                },
                'follow_up_date': quotation.follow_up_date,
                'created_at': quotation.created_at,
                'items': items
            }
            
            if term_ids:
                response_data['terms'] = term_ids
            
            return response_data
            
        except Exception as e:
            logger.error(f"Error preparing quotation response data: {str(e)}")
            basic_data = {
                'id': quotation.id,
                'quotation_number': quotation.quotation_number,
                'status': quotation.status,
                'total': float(quotation.total)
            }
            if term_ids:
                basic_data['terms'] = term_ids
            return basic_data