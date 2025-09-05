# File: quotation_create.py

from django.http import JsonResponse
from django.db import transaction
from django.conf import settings
import logging, traceback
from decimal import Decimal
from .views import BaseAPIView, JWTAuthMixin
from .models import Product, TermsAndConditions, ActivityLog, Quotation, Customer, Lead, ProductDetails
from .forms import QuotationForm, CustomerForm
from .choices import ActivityAction, LeadStatus
from .save_quotation import save_quotation_pdf
from .email_service import send_quotation_email
from apps.accounts.models import User, Roles

from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import IntegrityError
from django.db.models import Count

# FIX: Import the new refactored function
from .utils_quotation import (
    create_or_update_product_details,
    log_quotation_changes,
    validate_terms,
    calculate_totals_from_details,
    handle_validation_errors,
    get_quotation_response_data,
)

logger = logging.getLogger(__name__)


class QuotationCreate(JWTAuthMixin, BaseAPIView):
    @transaction.atomic
    def put(self, request):
        """
        Handles updating an existing Quotation.
        """
        try:
            request_json = getattr(request, 'json', {})
            if not request_json:
                return JsonResponse({"success": False, "error": "JSON data is required"}, status=400)

            quotation_id = request_json.get('quotation_id')
            if not quotation_id:
                return JsonResponse({"success": False, "error": "Quotation ID is required"}, status=400)

            try:
                quotation = Quotation.objects.get(id=quotation_id)
            except Quotation.DoesNotExist:
                return JsonResponse({"success": False, "error": "Quotation not found."}, status=404)

            # --- Customer Handling Logic ---
            customer_data = request_json.get("customer", {})
            customer_id = customer_data.get("id")
            if customer_id:
                try:
                    customer_instance = Customer.objects.get(id=customer_id)
                    customer_form = CustomerForm(customer_data, instance=customer_instance)
                except Customer.DoesNotExist:
                    return JsonResponse({"success": False, "error": f"Customer with id {customer_id} not found."}, status=404)
            else:
                customer_form = CustomerForm(customer_data)

            if customer_form.is_valid():
                customer = customer_form.save()
                logger.info(f"Customer {'created' if not customer_id else 'updated'}: {customer.id}")
            else:
                logger.error(f"Customer form validation failed: {customer_form.errors}")
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid customer data',
                    'customer_errors': customer_form.errors
                }, status=400)

            quotation_data = {k: v for k, v in request_json.items() if k not in [
                "items", "terms", "send_immediately", "auto_assign", "customer", "quotation_id"
            ]}
            items_data = request_json.get("items", [])
            terms_data = request_json.get("terms", [])
            valid_term_ids = validate_terms(terms_data)

            form = QuotationForm(quotation_data, instance=quotation)
            if not form.is_valid():
                return handle_validation_errors(form)

            quotation = form.save(commit=False)
            quotation.customer = customer
            
            # Save the main quotation fields first
            quotation.save(update_fields=[
                'assigned_to', 'email_template', 'discount', 'follow_up_date', 
                'status', 'discount_type', 'tax_rate', 'customer'
            ])

            if valid_term_ids is not None:
                quotation.terms.set(valid_term_ids)

            # Update product details if provided
            if items_data:
                create_or_update_product_details(quotation, items_data)
            
            # FIX: Use the refactored calculation logic
            totals = calculate_totals_from_details(quotation)
            quotation.subtotal = totals['subtotal']
            quotation.total = totals['total']
            quotation.save(update_fields=['subtotal', 'total']) # Save calculated totals

            logger.info(f"Quotation {quotation.quotation_number} updated successfully")
            
            # The lead is usually linked on creation, but we fetch it for the response
            lead = Lead.objects.filter(quotation_id=quotation.id).first()
            
            return JsonResponse({
                "success": True,
                "message": f"Quotation {quotation.quotation_number} updated successfully",
                "data": get_quotation_response_data(quotation, lead)
            }, status=200)

        except Exception as e:
            logger.error(f"Unexpected error in PUT: {str(e)}\n{traceback.format_exc()}")
            return JsonResponse({"success": False, "error": "Internal server error", "details": str(e)}, status=500)

    @transaction.atomic
    def post(self, request):
        try:
            request_json = getattr(request, 'json', {})
            if not request_json:
                return JsonResponse({'success': False, 'error': 'JSON data is required'}, status=400)

            customer_data = request_json.get('customer', {})
            customer_id = customer_data.get('id')
            customer_form = None
            if customer_id:
                try:
                    customer_instance = Customer.objects.get(id=customer_id)
                    customer_form = CustomerForm(customer_data, instance=customer_instance)
                except Customer.DoesNotExist:
                    return JsonResponse({"success": False, "error": f"Customer with id {customer_id} not found."}, status=404)
            else:
                customer_form = CustomerForm(customer_data)

            if customer_form.is_valid():
                customer = customer_form.save()
                logger.info(f"Customer {'created' if not customer_id else 'updated'}: {customer.id}")
            else:
                logger.error(f"Customer form validation failed: {customer_form.errors}")
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid customer data',
                    'customer_errors': customer_form.errors
                }, status=400)
            # --- End Customer Handling ---

            quotation_data = {k: v for k, v in request_json.items() if k not in [
                'items', 'terms', 'send_immediately', 'auto_assign', 'customer'
            ]}
            
            items_data = request_json.get('items', [])
            terms_data = request_json.get('terms', [])
            valid_term_ids = validate_terms(terms_data)

            form = QuotationForm(quotation_data)
            if not form.is_valid():
                return handle_validation_errors(form)

            quotation = form.save(commit=False)
            quotation.customer = customer
            
            # Auto-assignment logic
            user = request.user
            if getattr(user, 'role', None) == Roles.SALESPERSON:
                quotation.created_by = user
            
            if not quotation.assigned_to and request_json.get('auto_assign', True):
                if getattr(user, 'role', None) == Roles.SALESPERSON:
                    quotation.assigned_to = user
                else:
                    salesperson = User.objects.filter(role=Roles.SALESPERSON, is_active=True).annotate(num_quotations=Count('quotations')).order_by('num_quotations', 'id').first()
                    if salesperson:
                        quotation.assigned_to = salesperson
            
            # Save the quotation object to get an ID before creating related objects.
            quotation.save()

            # Create related ProductDetails
            if items_data:
                create_or_update_product_details(quotation, items_data)

            # Set ManyToMany terms
            if valid_term_ids:
                quotation.terms.set(valid_term_ids)
            
            # FIX: Use the refactored calculation logic after items are saved
            totals = calculate_totals_from_details(quotation)
            quotation.subtotal = totals['subtotal']
            quotation.total = totals['total']

            # Create associated Lead
            lead = Lead.objects.create(
                customer=customer, 
                assigned_to=quotation.assigned_to, 
                status=LeadStatus.PENDING, 
                created_by=user, 
                quotation_id=quotation.id
            )
            quotation.lead_id = lead.id

            # Handle PDF Generation
            pdf_url = None
            if items_data:
                try:
                    _, pdf_url = save_quotation_pdf(quotation, request, items_data=items_data, terms=valid_term_ids)
                    quotation.file_url = pdf_url
                    quotation.has_pdf = True
                except Exception as e:
                    logger.error(f"Failed to generate PDF: {str(e)}")
                    quotation.has_pdf = False
            
            # Final save with all computed/generated fields
            quotation.save(update_fields=['lead_id', 'file_url', 'has_pdf', 'subtotal', 'total'])
            
            log_quotation_changes(quotation, ActivityAction.QUOTATION_CREATED, user)

            if request_json.get('send_immediately'):
                quotation.refresh_from_db()
                try:
                    send_quotation_email(quotation)
                    ActivityLog.log(
                        actor=user, 
                        action=ActivityAction.QUOTATION_SENT, 
                        entity=quotation, 
                        message=f"Quotation {quotation.quotation_number} sent immediately"
                    )
                except Exception as e:
                    logger.error(f"Failed to send email: {str(e)}")

            response_data = get_quotation_response_data(quotation, lead)

            logger.info(f"Quotation {quotation.quotation_number} created successfully")
            return JsonResponse({
                'success': True, 
                'message': f"Quotation {quotation.quotation_number} created successfully", 
                'data': response_data
            }, status=201)

        except Exception as e:
            logger.error(f"Unexpected error in POST: {str(e)}\n{traceback.format_exc()}")
            return JsonResponse({"success": False, "error": "Internal server error", "details": str(e)}, status=500)