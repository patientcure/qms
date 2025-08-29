from django.http import JsonResponse
from django.db import transaction
from django.conf import settings
import json
import logging
from .models import Product, TermsAndConditions, ActivityLog, Quotation, Customer, Lead
from .forms import QuotationForm
from .choices import ActivityAction, LeadStatus
from .save_quotation import save_quotation_pdf
from .views import BaseAPIView
from .forms import CustomerForm
logger = logging.getLogger(__name__)
from apps.accounts.models import User, Roles
from django.db.models import Count
from decimal import Decimal
from .email_service import send_quotation_email

class QuotationCreateView(BaseAPIView):
    @transaction.atomic
    def put(self, request):
        try:
            request_json = getattr(request, 'json', {})
            if not request_json:
                return JsonResponse({
                    'success': False,
                    'error': 'JSON data is required'
                }, status=400)

            quotation_id = request_json.get('id') or request_json.get('quotation_id')
            if not quotation_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Quotation ID is required for update.'
                }, status=400)

            quotation = Quotation.objects.filter(id=quotation_id).first()
            if not quotation:
                return JsonResponse({
                    'success': False,
                    'error': 'Quotation not found.'
                }, status=404)

            form_data = {**request.POST.dict(), **request_json}
            customer_data = form_data.get('customer', {})
            if not isinstance(customer_data, dict):
                customer_data = {}
            phone = customer_data.get('phone')
            if not phone:
                return JsonResponse({
                    'success': False,
                    'error': 'Customer phone is required'
                }, status=400)

            customer, _ = Customer.objects.get_or_create(
                phone=phone,
                defaults={k: v for k, v in customer_data.items() if k != 'phone'}
            )
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
            terms_data = request_json.get('terms', [])
            valid_term_ids = self._validate_terms(terms_data)

            send_immediately = request_json.get('send_immediately', False)
            auto_assign = request_json.get('auto_assign', True)

            form = QuotationForm(quotation_data, instance=quotation)
            if not form.is_valid():
                return self._handle_validation_errors(form)

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
            
            lead = None # Initialize lead variable
            user = request.user if hasattr(request, 'user') and request.user.is_authenticated else None
            if quotation.lead_id:
                try:
                    lead = Lead.objects.get(id=quotation.lead_id)
                    lead.customer = customer
                    lead.assigned_to = quotation.assigned_to
                    lead.save(update_fields=['customer', 'assigned_to'])
                except Lead.DoesNotExist:
                    quotation.lead_id = None # Stale ID, will be recreated
            
            if not quotation.lead_id:
                lead = Lead.objects.create(
                    customer=customer,
                    assigned_to=quotation.assigned_to,
                    status=LeadStatus.PENDING,
                    created_by=user,
                    quotation_id=quotation.id
                )
                quotation.lead_id = lead.id

            super(Quotation, quotation).save()
            product_ids = [item.get('product') for item in items_data if item.get('product')]
            quotation.product.set(product_ids)

            self._recalculate_totals_from_items(quotation, items_data)

            if valid_term_ids:
                quotation.terms.set(valid_term_ids)

            if user:
                ActivityLog.log(
                    actor=user,
                    action=ActivityAction.QUOTATION_UPDATED,
                    entity=quotation,
                    message="Updated via API"
                )

            # --- Conditional PDF Generation ---
            pdf_url = None
            if items_data:
                try:
                    pdf_path, pdf_url = save_quotation_pdf(quotation, request, items_data=items_data, terms=valid_term_ids)
                    quotation.file_url = pdf_url
                    quotation.has_pdf = True
                except Exception as e:
                    logger.error(f"PDF generation failed: {str(e)}")
                    quotation.has_pdf = False
            else:
                quotation.file_url = ''
                quotation.has_pdf = False
            
            quotation.save(update_fields=['file_url', 'has_pdf', 'lead_id'])

            if send_immediately:
                quotation.refresh_from_db()
                send_quotation_email(quotation)

            # CORRECTED LINE
            quotation_data = self._get_quotation_response_data(quotation, lead, items_data, valid_term_ids)
            quotation_data['pdf_url'] = pdf_url

            return JsonResponse({
                'success': True,
                'message': f"Quotation {quotation.quotation_number} updated successfully",
                'data': quotation_data
            }, status=200)

        except Exception as e:
            logger.error(f"Error in QuotationCreateView PUT: {str(e)}", exc_info=True)
            error_response = {'success': False, 'error': f"Internal server error: {str(e)}"}
            if settings.DEBUG:
                import traceback
                error_response['debug_info'] = traceback.format_exc()
            return JsonResponse(error_response, status=500)

    @transaction.atomic
    def post(self, request):
        try:
            request_json = getattr(request, 'json', {})
            if not request_json:
                return JsonResponse({'success': False, 'error': 'JSON data is required'}, status=400)

            form_data = {**request.POST.dict(), **request_json}

            # --- Customer Handling ---
            customer_data = form_data.get('customer', {})
            if not isinstance(customer_data, dict):
                customer_data = {}
            phone = customer_data.get('phone')
            if not phone:
                return JsonResponse({'success': False, 'error': 'Customer phone is required'}, status=400)

            customer, created = Customer.objects.get_or_create(
                phone=phone,
                defaults={k: v for k, v in customer_data.items() if k != 'phone'}
            )
            if not created: # If customer exists, update their info
                for key, value in customer_data.items():
                    setattr(customer, key, value)
                customer.save()
            customer_id = customer.id

            # --- Quotation Handling ---
            quotation_data = {k: v for k, v in form_data.items()
                              if k not in ['items', 'terms', 'send_immediately', 'auto_assign', 'customer']}
            quotation_data['customer'] = customer_id

            required_fields = ['customer', 'status']
            missing_fields = [f for f in required_fields if not quotation_data.get(f)]
            if missing_fields:
                return JsonResponse({'success': False, 'error': f'Missing required fields: {missing_fields}'}, status=400)

            items_data = request_json.get('items', [])
            terms_data = request_json.get('terms', [])
            valid_term_ids = self._validate_terms(terms_data)

            send_immediately = request_json.get('send_immediately', False)
            auto_assign = request_json.get('auto_assign', True)

            form = QuotationForm(quotation_data)
            if not form.is_valid():
                return self._handle_validation_errors(form)

            quotation = form.save(commit=False)

            if not quotation.quotation_number:
                from .utils import generate_next_quotation_number
                quotation.quotation_number = generate_next_quotation_number()

            if not quotation.assigned_to and auto_assign:
                salesperson = (
                    User.objects.filter(role=Roles.SALESPERSON, is_active=True)
                    .annotate(num_quotations=Count('quotations'))
                    .order_by('num_quotations', 'id')
                    .first()
                )
                if salesperson:
                    quotation.assigned_to = salesperson

            super(Quotation, quotation).save() # Initial save to get an ID

            # --- Lead Creation ---
            user = request.user if hasattr(request, 'user') and request.user.is_authenticated else None
            lead = Lead.objects.create(
                customer=customer,
                assigned_to=quotation.assigned_to,
                status=LeadStatus.PENDING,
                created_by=user,
                quotation_id=quotation.id
            )
            quotation.lead_id = lead.id

            product_ids = [item.get('product') for item in items_data if item.get('product')]
            quotation.product.set(product_ids)
            self._recalculate_totals_from_items(quotation, items_data)

            if valid_term_ids:
                quotation.terms.set(valid_term_ids)

            if user:
                ActivityLog.log(
                    actor=user,
                    action=ActivityAction.QUOTATION_CREATED,
                    entity=quotation,
                    message="Created via API"
                )

            # --- Conditional PDF Generation ---
            pdf_url = None
            if items_data:
                try:
                    pdf_path, pdf_url = save_quotation_pdf(quotation, request, items_data=items_data, terms=valid_term_ids)
                    quotation.file_url = pdf_url
                    quotation.has_pdf = True
                except Exception as e:
                    logger.error(f"PDF generation failed: {str(e)}")
                    quotation.has_pdf = False
            else:
                quotation.has_pdf = False

            quotation.save(update_fields=['lead_id', 'file_url', 'has_pdf'])

            if send_immediately:
                quotation.refresh_from_db()
                send_quotation_email(quotation)

            # CORRECTED LINE
            quotation_data = self._get_quotation_response_data(quotation, lead, items_data, valid_term_ids)
            quotation_data['pdf_url'] = pdf_url

            return JsonResponse({
                'success': True,
                'message': f"Quotation {quotation.quotation_number} created successfully",
                'data': quotation_data
            }, status=201)

        except Exception as e:
            logger.error(f"Error in QuotationCreateView POST: {str(e)}", exc_info=True)
            error_response = {'success': False, 'error': f"Internal server error: {str(e)}"}
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
            return list(TermsAndConditions.objects.filter(id__in=term_ids).values_list('id', flat=True))
        except (ValueError, TypeError):
            return []

    def _recalculate_totals_from_items(self, quotation, items_data):
        if not items_data:
            quotation.subtotal = Decimal('0.00')
            quotation.tax_total = Decimal('0.00')
            quotation.total = Decimal('0.00')
            quotation.save(update_fields=['subtotal', 'tax_total', 'total'])
            return

        product_ids = [item.get('product') for item in items_data if item.get('product')]
        products = {p.id: p for p in Product.objects.filter(id__in=product_ids)}

        subtotal = Decimal('0.00')
        tax_total = Decimal('0.00')

        for item in items_data:
            product = products.get(item.get('product'))
            if not product:
                continue

            quantity = Decimal(str(item.get('quantity', 1)))

            unit_price_from_request = item.get('unit_price')
            unit_price = (
                Decimal(str(unit_price_from_request))
                if unit_price_from_request is not None
                else product.selling_price
            )

            tax_rate_from_request = item.get('tax_rate')
            tax_rate = (
                Decimal(str(tax_rate_from_request))
                if tax_rate_from_request is not None
                else product.tax_rate
            )

            line_total = quantity * unit_price
            line_tax = line_total * (tax_rate / Decimal('100.00'))

            subtotal += line_total
            tax_total += line_tax

        quotation.subtotal = subtotal.quantize(Decimal('0.01'))
        quotation.tax_total = tax_total.quantize(Decimal('0.01'))

        discount_amount = Decimal('0.00')
        if quotation.discount:
            discount_amount = (subtotal * quotation.discount / Decimal('100.00')).quantize(Decimal('0.01'))

        quotation.total = ((subtotal - discount_amount) + tax_total).quantize(Decimal('0.01'))

        quotation.save(update_fields=['subtotal', 'tax_total', 'total'])

    def _handle_validation_errors(self, form):
        errors = {'form': form.errors}
        return JsonResponse({'success': False, 'errors': errors}, status=400)

    def _get_quotation_response_data(self, quotation, lead, items_data, term_ids=None):
        try:
            product_ids = [item.get('product') for item in items_data if item.get('product')]
            products = {p.id: p for p in Product.objects.filter(id__in=product_ids)}
            
            items = []
            for item_data in items_data:
                product = products.get(item_data.get('product'))
                if not product:
                    continue

                quantity = Decimal(str(item_data.get('quantity', 1)))

                unit_price_from_request = item_data.get('unit_price')
                unit_price = (
                    Decimal(str(unit_price_from_request))
                    if unit_price_from_request is not None
                    else product.selling_price
                )

                tax_rate_from_request = item_data.get('tax_rate')
                tax_rate = (
                    Decimal(str(tax_rate_from_request))
                    if tax_rate_from_request is not None
                    else product.tax_rate
                )

                line_total = quantity * unit_price
                line_tax = line_total * (tax_rate / Decimal('100.00'))

                items.append({
                    'product': {'id': product.id, 'name': product.name},
                    'description': item_data.get('description', product.name),
                    'quantity': float(quantity),
                    'unit_price': float(unit_price),
                    'tax_rate': float(tax_rate),
                    'line_total': float(line_total.quantize(Decimal('0.01'))),
                    'line_tax': float(line_tax.quantize(Decimal('0.01'))),
                    'line_total_with_tax': float((line_total + line_tax).quantize(Decimal('0.01')))
                })

            response_data = {
                'id': quotation.id,
                'quotation_number': quotation.quotation_number,
                'status': quotation.status,
                'subtotal': float(quotation.subtotal),
                'tax_total': float(quotation.tax_total),
                'total': float(quotation.total),
                'discount': float(quotation.discount) if quotation.discount else 0.0,
                'currency': quotation.currency,
                'customer': {
                    'id': quotation.customer.id,
                    'name': quotation.customer.name,
                    'email': quotation.customer.email,
                    'phone': quotation.customer.phone
                },
                'assigned_to': {
                    'id': quotation.assigned_to.id,
                    'name': quotation.assigned_to.get_full_name()
                } if quotation.assigned_to else None,
                'lead': {
                    'id': lead.id,
                    'status': lead.status,
                    'priority': lead.priority,
                    'follow_up_date': lead.follow_up_date,
                    'quotation_id': lead.quotation_id,
                    'notes': lead.notes
                } if lead else None,
                'follow_up_date': quotation.follow_up_date,
                'created_at': quotation.created_at,
                'items': items,
                'terms': term_ids if term_ids else []
            }
            return response_data

        except Exception as e:
            logger.error(f"Error preparing quotation response data: {str(e)}")
            return {'id': quotation.id, 'quotation_number': quotation.quotation_number, 'error': 'Failed to serialize response'}