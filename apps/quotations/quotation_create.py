# File: quotation_create.py

from django.http import JsonResponse
from django.db import transaction
from django.conf import settings
import logging, traceback
from decimal import Decimal
from django.db.models import Count
from django.core.exceptions import ObjectDoesNotExist

from .views import BaseAPIView, JWTAuthMixin
from .models import Product, TermsAndConditions, ActivityLog, Quotation, Customer, Lead, ProductDetails
from .forms import QuotationForm, CustomerForm
from .choices import ActivityAction, LeadStatus, QuotationStatus
from .save_quotation import save_quotation_pdf
from .email_service import send_quotation_email
from apps.accounts.models import User, Roles

# Import refactored functions
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
    """
    Handles the creation and updating of Quotations.
    """

    def _handle_customer(self, customer_data):
        """
        Gets, creates, or updates a customer based on the phone number.
        Returns a tuple: (customer_object, error_response).
        """
        phone = customer_data.get("phone")
        if not phone:
            return None, JsonResponse({'success': False, 'error': 'Customer phone number is required.'}, status=400)

        try:
            customer, created = Customer.objects.update_or_create(
                phone=phone, defaults={k: v for k, v in customer_data.items() if v is not None}
            )
            logger.info(f"Customer {'created' if created else 'updated'}: {customer.phone}")
            return customer, None
        except Exception as e:
            logger.error(f"Customer data handling failed: {e}")
            return None, JsonResponse({'success': False, 'error': 'Invalid customer data.'}, status=400)

    def _process_quotation_data(self, quotation, request, user, action):
        """
        A centralized method to handle the shared logic of processing quotation details.
        Modifies the quotation instance in-memory.
        """
        request_json = getattr(request, 'json', {})
        items_data = request_json.get("items", [])
        terms_data = request_json.get("terms", [])
        send_immediately = request_json.get('send_immediately', False)

        # 1. Set Terms and Items
        valid_term_ids = validate_terms(terms_data)
        if valid_term_ids is not None:
            quotation.terms.set(valid_term_ids)
        
        if items_data:
            create_or_update_product_details(quotation, items_data)

        # 2. Calculate Totals
        totals = calculate_totals_from_details(quotation)
        quotation.subtotal = totals['subtotal']
        quotation.total = totals['total']

        # 3. Generate PDF
        if items_data:
            try:
                _, pdf_url = save_quotation_pdf(quotation, request, items_data=items_data, terms=valid_term_ids)
                quotation.file_url = pdf_url
                quotation.has_pdf = True
            except Exception as e:
                logger.error(f"Failed to generate PDF for Quotation {quotation.id}: {e}")
                quotation.has_pdf = False
        
        # 4. Log Activity
        log_quotation_changes(quotation, action, user)

        quotation.save(update_fields=['subtotal', 'total', 'file_url', 'has_pdf'])
        if send_immediately:

            quotation.refresh_from_db() 
            try:
                send_quotation_email(quotation)
                ActivityLog.log(
                    actor=user,
                    action=ActivityAction.QUOTATION_SENT,
                    entity=quotation,
                    message=f"Quotation {quotation.quotation_number} sent to customer.",
                    customer=quotation.customer,
                )
            except Exception as e:
                logger.error(f"Failed to send email for Quotation {quotation.id}: {e}")

    @transaction.atomic
    def post(self, request):
        """
        Handles creating a new Quotation.
        """
        try:
            request_json = getattr(request, 'json', {})
            user = request.user
            send_immediately = request_json.get('send_immediately', False)

            # Step 1: Handle Customer
            customer, error_response = self._handle_customer(request_json.get("customer", {}))
            if error_response:
                return error_response

            # Step 2: Validate and prepare Quotation object
            quotation_data = {k: v for k, v in request_json.items() if k not in [
                'items', 'terms', 'send_immediately', 'auto_assign', 'customer'
            ]}
            form = QuotationForm(quotation_data)
            if not form.is_valid():
                return handle_validation_errors(form)

            quotation = form.save(commit=False)
            quotation.customer = customer
            quotation.created_by = user

            # Step 3: Always create as DRAFT. Status is updated later if sent immediately.
            quotation.status = QuotationStatus.DRAFT

            # Step 4: Handle assignment
            if not quotation.assigned_to and request_json.get('auto_assign', True):
                if getattr(user, 'role', None) == Roles.SALESPERSON:
                    quotation.assigned_to = user
                else:
                    salesperson = User.objects.filter(role=Roles.SALESPERSON, is_active=True).annotate(
                        num_quotations=Count('quotations')
                    ).order_by('num_quotations', 'id').first()
                    quotation.assigned_to = salesperson
            
            quotation.save() # Initial save to get an ID

            # Step 5: Create Lead and update status ONLY if send_immediately is true
            lead = None
            if send_immediately:
                quotation.status = QuotationStatus.PENDING # Initial "sent" status
                lead = Lead.objects.create(
                    customer=customer, 
                    assigned_to=quotation.assigned_to, 
                    status=LeadStatus.PENDING, 
                    created_by=user, 
                    quotation_id=quotation.id,
                    follow_up_date=quotation.follow_up_date
                )
                quotation.lead_id = lead.id

            # Step 6: Process items, totals, PDF, and email
            self._process_quotation_data(quotation, request, user, action=ActivityAction.QUOTATION_CREATED)
            
            # Step 7: Final save with all updated fields
            quotation.save()

            logger.info(f"Quotation {quotation.quotation_number} created successfully")
            return JsonResponse({
                'success': True, 
                'message': f"Quotation {quotation.quotation_number} created successfully", 
                'data': get_quotation_response_data(quotation, lead)
            }, status=201)

        except Exception as e:
            logger.error(f"Unexpected error in POST: {e}\n{traceback.format_exc()}")
            return JsonResponse({"success": False, "error": "Internal server error"}, status=500)


    @transaction.atomic
    def put(self, request):
        """
        Handles updating an existing Quotation.
        """
        try:
            request_json = getattr(request, 'json', {})
            user = request.user
            quotation_id = request_json.get('quotation_id')
            send_immediately = request_json.get('send_immediately', False)

            if not quotation_id:
                return JsonResponse({"success": False, "error": "Quotation ID is required"}, status=400)
            
            quotation = Quotation.objects.get(id=quotation_id)
            original_status = quotation.status
            
            # Step 1: Handle Customer
            customer, error_response = self._handle_customer(request_json.get("customer", {}))
            if error_response:
                return error_response
            
            # Step 2: Validate and prepare Quotation object
            quotation_data = {k: v for k, v in request_json.items() if k not in [
                "items", "terms", "send_immediately", "auto_assign", "customer", "quotation_id"
            ]}
            form = QuotationForm(quotation_data, instance=quotation)
            if not form.is_valid():
                return handle_validation_errors(form)

            quotation = form.save(commit=False)
            quotation.customer = customer
            
            # Step 3: Handle status updates and lead creation logic
            lead = Lead.objects.filter(quotation_id=quotation.id).first()
            
            if original_status == QuotationStatus.DRAFT and send_immediately:
                # First time sending a DRAFT quotation. Create lead and update status.
                quotation.status = QuotationStatus.PENDING
                
                if not lead:
                    lead = Lead.objects.create(
                        customer=customer, 
                        assigned_to=quotation.assigned_to, 
                        status=LeadStatus.PENDING, 
                        created_by=user, 
                        quotation_id=quotation.id,
                        follow_up_date=quotation.follow_up_date
                    )
                    quotation.lead_id = lead.id

            elif original_status != QuotationStatus.DRAFT:
                # Any update to an already-sent quotation marks it as REVISED.
                quotation.status = QuotationStatus.REVISED
                if lead:
                    lead.status = LeadStatus.REVISED
                    lead.save(update_fields=['status'])

            # Step 4: Process items, totals, PDF, and email
            self._process_quotation_data(quotation, request, user, action=ActivityAction.QUOTATION_UPDATED)

            # Step 5: Final Save with all updates
            quotation.save()

            logger.info(f"Quotation {quotation.quotation_number} updated successfully")
            return JsonResponse({
                "success": True,
                "message": f"Quotation {quotation.quotation_number} updated successfully",
                "data": get_quotation_response_data(quotation, lead)
            }, status=200)

        except Quotation.DoesNotExist:
            return JsonResponse({"success": False, "error": "Quotation not found."}, status=404)
        except Exception as e:
            logger.error(f"Unexpected error in PUT: {e}\n{traceback.format_exc()}")
            return JsonResponse({"success": False, "error": "Internal server error"}, status=500)