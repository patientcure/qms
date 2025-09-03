from django.http import JsonResponse
from django.db import transaction
from django.conf import settings
import json
import logging
from .models import Product, TermsAndConditions, ActivityLog, Quotation, Customer, Lead, ProductDetails
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
    def _create_or_update_product_details(self, quotation, items_data):
        if not quotation._state.adding:
            quotation.details.all().delete()

        product_ids = [item.get('product') for item in items_data if item.get('product')]
        products_cache = {p.id: p for p in Product.objects.filter(id__in=product_ids)}
        
        product_details_to_create = []
        for item_data in items_data:
            product_id = item_data.get('product')
            product_obj = products_cache.get(product_id)
            
            if not product_obj and item_data.get('name'):
                 product_obj, created = Product.objects.get_or_create(
                     name=item_data['name'],
                     defaults={'selling_price': item_data.get('unit_price', 0)}
                 )

            if not product_obj:
                continue

            product_details_to_create.append(
                ProductDetails(
                    quotation=quotation,
                    product=product_obj,
                    quantity=item_data.get('quantity', 1),
                    unit_price=item_data.get('unit_price', product_obj.selling_price),
                    selling_price=product_obj.selling_price,
                    discount=item_data.get('discount', 0)
                )
            )
        
        if product_details_to_create:
            ProductDetails.objects.bulk_create(product_details_to_create)

    # The PUT and POST methods remain the same, only the call to recalculate will now use the new logic.
    @transaction.atomic
    def put(self, request):
        try:
            request_json = getattr(request, 'json', {})
            if not request_json:
                return JsonResponse({'success': False, 'error': 'JSON data is required'}, status=400)

            quotation_id = request_json.get('id') or request_json.get('quotation_id')
            if not quotation_id:
                return JsonResponse({'success': False, 'error': 'Quotation ID is required for update.'}, status=400)

            quotation = Quotation.objects.filter(id=quotation_id).first()
            if not quotation:
                return JsonResponse({'success': False, 'error': 'Quotation not found.'}, status=404)

            form_data = {**request.POST.dict(), **request_json}
            customer_data = form_data.get('customer', {})
            phone = customer_data.get('phone')
            if not phone:
                return JsonResponse({'success': False, 'error': 'Customer phone is required'}, status=400)

            customer, _ = Customer.objects.get_or_create(
                phone=phone,
                defaults={k: v for k, v in customer_data.items() if k != 'phone'}
            )
            
            quotation_data = {k: v for k, v in form_data.items() if k not in ['items', 'terms', 'send_immediately', 'auto_assign', 'customer']}
            quotation_data['customer'] = customer.id

            items_data = request_json.get('items', [])
            terms_data = request_json.get('terms', [])
            valid_term_ids = self._validate_terms(terms_data)

            form = QuotationForm(form_data, instance=quotation)
            if not form.is_valid():
                return self._handle_validation_errors(form)

            quotation = form.save()
            
            self._create_or_update_product_details(quotation, items_data)
            
            quotation_details = quotation.details.select_related('product').all()
            clean_items_data = [
                {'product': detail.product.id, 'name': detail.product.name, 'quantity': detail.quantity, 'unit_price': detail.unit_price, 'discount': detail.discount}
                for detail in quotation_details
            ]
            
            self._recalculate_totals_from_items(quotation, clean_items_data)

            if valid_term_ids:
                quotation.terms.set(valid_term_ids)

            pdf_url = None
            if clean_items_data:
                try:
                    _, pdf_url = save_quotation_pdf(quotation, request, items_data=clean_items_data, terms=valid_term_ids)
                    quotation.file_url = pdf_url
                    quotation.has_pdf = True
                except Exception as e:
                    logger.error(f"PDF generation failed: {str(e)}")
                    quotation.has_pdf = False
            else:
                quotation.file_url = ''
                quotation.has_pdf = False
            
            quotation.save(update_fields=['file_url', 'has_pdf'])

            if request_json.get('send_immediately'):
                quotation.refresh_from_db()
                send_quotation_email(quotation)

            quotation_data = self._get_quotation_response_data(quotation, quotation.lead, valid_term_ids)
            quotation_data['pdf_url'] = pdf_url

            return JsonResponse({'success': True, 'message': f"Quotation {quotation.quotation_number} updated successfully", 'data': quotation_data}, status=200)

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
            customer_data = form_data.get('customer', {})
            phone = customer_data.get('phone')
            if not phone:
                return JsonResponse({'success': False, 'error': 'Customer phone is required'}, status=400)

            customer, created = Customer.objects.get_or_create(
                phone=phone,
                defaults={k: v for k, v in customer_data.items() if k != 'phone'}
            )
            if not created:
                for key, value in customer_data.items():
                    setattr(customer, key, value)
                customer.save()

            quotation_data = {k: v for k, v in form_data.items() if k not in ['items', 'terms', 'send_immediately', 'auto_assign', 'customer']}
            quotation_data['customer'] = customer.id
            
            items_data = request_json.get('items', [])
            terms_data = request_json.get('terms', [])
            valid_term_ids = self._validate_terms(terms_data)

            form = QuotationForm(quotation_data)
            if not form.is_valid():
                return self._handle_validation_errors(form)

            quotation = form.save(commit=False)

            if not quotation.quotation_number:
                from .utils import generate_next_quotation_number
                quotation.quotation_number = generate_next_quotation_number()

            if not quotation.assigned_to and request_json.get('auto_assign', True):
                salesperson = User.objects.filter(role=Roles.SALESPERSON, is_active=True).annotate(num_quotations=Count('quotations')).order_by('num_quotations', 'id').first()
                if salesperson:
                    quotation.assigned_to = salesperson

            quotation.save()

            user = request.user if hasattr(request, 'user') and request.user.is_authenticated else None
            lead = Lead.objects.create(customer=customer, assigned_to=quotation.assigned_to, status=LeadStatus.PENDING, created_by=user, quotation_id=quotation.id)
            quotation.lead_id = lead.id

            self._create_or_update_product_details(quotation, items_data)
            
            quotation_details = quotation.details.select_related('product').all()
            clean_items_data = [
                {'product': detail.product.id, 'name': detail.product.name, 'quantity': detail.quantity, 'unit_price': detail.unit_price, 'discount': detail.discount}
                for detail in quotation_details
            ]
            
            self._recalculate_totals_from_items(quotation, clean_items_data)

            if valid_term_ids:
                quotation.terms.set(valid_term_ids)

            pdf_url = None
            if clean_items_data:
                try:
                    _, pdf_url = save_quotation_pdf(quotation, request, items_data=clean_items_data, terms=valid_term_ids)
                    quotation.file_url = pdf_url
                    quotation.has_pdf = True
                except Exception as e:
                    logger.error(f"PDF generation failed: {str(e)}")
                    quotation.has_pdf = False
            else:
                quotation.has_pdf = False

            quotation.save(update_fields=['lead_id', 'file_url', 'has_pdf'])

            if request_json.get('send_immediately'):
                quotation.refresh_from_db()
                send_quotation_email(quotation)

            quotation_data = self._get_quotation_response_data(quotation, lead, valid_term_ids)
            quotation_data['pdf_url'] = pdf_url

            return JsonResponse({'success': True, 'message': f"Quotation {quotation.quotation_number} created successfully", 'data': quotation_data}, status=201)

        except Exception as e:
            logger.error(f"Error in QuotationCreateView POST: {str(e)}", exc_info=True)
            error_response = {'success': False, 'error': f"Internal server error: {str(e)}"}
            if settings.DEBUG:
                import traceback
                error_response['debug_info'] = traceback.format_exc()
            return JsonResponse(error_response, status=500)
            
    def _validate_terms(self, terms_data):
        if not terms_data: return []
        try:
            if isinstance(terms_data, str):
                term_ids = [int(x.strip()) for x in terms_data.split(',') if x.strip()]
            elif isinstance(terms_data, list):
                term_ids = [int(x) for x in terms_data if str(x).strip()]
            else: return []
            return list(TermsAndConditions.objects.filter(id__in=term_ids).values_list('id', flat=True))
        except (ValueError, TypeError): return []

    def _recalculate_totals_from_items(self, quotation, items_data):
        # --- MODIFIED: Calculation logic updated to subtract discount last ---
        if not items_data:
            quotation.subtotal = Decimal('0.00')
            quotation.total = Decimal('0.00')
            quotation.save(update_fields=['subtotal', 'total'])
            return

        gross_subtotal = Decimal('0.00')
        total_item_discount = Decimal('0.00')

        for item in items_data:
            quantity = Decimal(str(item.get('quantity', 1)))
            unit_price = Decimal(str(item.get('unit_price', '0.00')))
            item_discount_percent = Decimal(str(item.get('discount', '0.00')))

            line_gross_total = quantity * unit_price
            item_discount_amount = line_gross_total * (item_discount_percent / 100)
            
            gross_subtotal += line_gross_total
            total_item_discount += item_discount_amount

        subtotal_after_item_disc = gross_subtotal - total_item_discount

        # 1. Calculate tax amount based on subtotal (after item discounts)
        tax_amount = Decimal('0.00')
        if quotation.tax_rate and quotation.tax_rate > 0:
            tax_amount = subtotal_after_item_disc * (quotation.tax_rate / Decimal('100.00'))

        # 2. Calculate the base for the final discount
        total_before_overall_discount = subtotal_after_item_disc + tax_amount
        
        # 3. Calculate overall discount amount (base is pre-tax subtotal)
        overall_discount_amount = Decimal('0.00')
        if quotation.discount and quotation.discount > 0:
            if quotation.discount_type == 'amount':
                overall_discount_amount = quotation.discount
            else: # Percentage
                overall_discount_amount = (subtotal_after_item_disc * quotation.discount / Decimal('100.00'))

        # 4. Calculate final total by subtracting the discount last
        final_total = total_before_overall_discount - overall_discount_amount

        # Save the calculated values
        quotation.subtotal = gross_subtotal.quantize(Decimal('0.01'))
        quotation.total = final_total.quantize(Decimal('0.01'))
        quotation.save(update_fields=['subtotal', 'total'])

    def _handle_validation_errors(self, form):
        errors = {'form': form.errors}
        return JsonResponse({'success': False, 'errors': errors}, status=400)

    def _get_quotation_response_data(self, quotation, lead, term_ids=None):
        # --- MODIFIED: To reflect the new calculation order in the response ---
        try:
            items = []
            gross_subtotal = Decimal('0.00')
            for detail in quotation.details.select_related('product').all():
                product = detail.product
                quantity = Decimal(str(detail.quantity))
                unit_price = Decimal(str(detail.unit_price))
                discount_percent = Decimal(str(detail.discount or '0.00'))
                
                gross_total = quantity * unit_price
                gross_subtotal += gross_total
                discount_amount = gross_total * (discount_percent / 100)
                net_total = gross_total - discount_amount

                items.append({
                    'product': {'id': product.id, 'name': product.name},
                    'description': product.name, 'quantity': float(quantity),
                    'unit_price': float(unit_price), 'discount': float(discount_percent),
                    'line_total': float(net_total.quantize(Decimal('0.01'))),
                })
            
            # Re-calculate totals for accurate response data with the new order
            subtotal_after_item_disc = sum(Decimal(str(it['line_total'])) for it in items)
            
            tax_amount = subtotal_after_item_disc * ((quotation.tax_rate or 0) / 100)

            total_before_overall_discount = subtotal_after_item_disc + tax_amount

            overall_discount_amount = Decimal('0.00')
            if quotation.discount and quotation.discount > 0:
                if quotation.discount_type == 'amount':
                    overall_discount_amount = quotation.discount
                else: # Percentage base is pre-tax subtotal
                    overall_discount_amount = subtotal_after_item_disc * (quotation.discount / 100)
            
            final_total = total_before_overall_discount - overall_discount_amount

            response_data = {
                'id': quotation.id, 'quotation_number': quotation.quotation_number,
                'status': quotation.status, 'subtotal': float(gross_subtotal.quantize(Decimal('0.01'))),
                'tax_rate': float(quotation.tax_rate or 0),
                'tax_total': float(tax_amount.quantize(Decimal('0.01'))),
                'total': float(final_total.quantize(Decimal('0.01'))),
                'discount': float(quotation.discount) if quotation.discount else 0.0,
                'discount_type': quotation.discount_type, 'currency': quotation.currency,
                'customer': {'id': quotation.customer.id, 'name': quotation.customer.name, 'email': quotation.customer.email, 'phone': quotation.customer.phone},
                'assigned_to': {'id': quotation.assigned_to.id, 'name': quotation.assigned_to.get_full_name()} if quotation.assigned_to else None,
                'lead': {'id': lead.id, 'status': lead.status, 'priority': lead.priority, 'follow_up_date': lead.follow_up_date, 'quotation_id': lead.quotation_id, 'notes': lead.notes} if lead else None,
                'follow_up_date': quotation.follow_up_date, 'created_at': quotation.created_at,
                'items': items, 'terms': term_ids if term_ids else []
            }
            return response_data

        except Exception as e:
            logger.error(f"Error preparing quotation response data: {str(e)}")
            return {'id': quotation.id, 'quotation_number': quotation.quotation_number, 'error': 'Failed to serialize response'}