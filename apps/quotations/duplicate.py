from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import (
    ActivityLog,
    Lead,
    ProductDetails,
    Quotation,
    QuotationLeadLink,
)
from .choices import ActivityAction, LeadStatus, QuotationStatus


class DuplicateQuotationAPIView(APIView):
    """
    An endpoint to create a duplicate of a specific quotation.
    
    Accepts a POST request and returns the ID of the newly created quotation.
    e.g., POST /api/quotations/123/duplicate/
    """

    @transaction.atomic
    def post(self, request, pk, *args, **kwargs):
        """
        Finds the original quotation by its primary key (pk), creates a deep copy
        and keeps it attached to the original quotation's lead.
        """
        try:
            # Step 1: Retrieve the original quotation and its related items efficiently.
            original_quotation = get_object_or_404(
                Quotation.objects.prefetch_related('details', 'terms'), 
                pk=pk
            )
            requested_lead_id = kwargs.get('lead_id')
            if requested_lead_id and not (
                original_quotation.lead_id == requested_lead_id
                or QuotationLeadLink.objects.filter(
                    quotation=original_quotation,
                    lead_id=requested_lead_id,
                ).exists()
            ):
                return Response(
                    {"error": "Quotation is not linked to this lead."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            original_product_details = list(original_quotation.details.all())
            original_terms = list(original_quotation.terms.all())

            # Revisions stay under the same lead; never create a second lead.
            lead_id = requested_lead_id or original_quotation.lead_id
            if not lead_id:
                lead_id = QuotationLeadLink.objects.filter(
                    quotation=original_quotation
                ).values_list('lead_id', flat=True).first()
            lead = Lead.objects.filter(pk=lead_id).first()

            # Step 3: Create a new quotation instance, copying necessary fields.
            new_quotation = Quotation(
                customer=original_quotation.customer,
                assigned_to=original_quotation.assigned_to,
                email_template=original_quotation.email_template,
                follow_up_date=original_quotation.follow_up_date,
                discount_type=original_quotation.discount_type,
                currency=original_quotation.currency,
                subtotal=original_quotation.subtotal,
                tax_rate=original_quotation.tax_rate,
                total=original_quotation.total,
                discount=original_quotation.discount,
                lead_id=lead.pk if lead else None,
                file_url= original_quotation.file_url,
                status=QuotationStatus.SENT,
            )
            new_quotation.save()

            if lead:
                original_quotation.status = QuotationStatus.REVISED
                original_quotation.save(update_fields=['status'])
                lead.quotation_id = new_quotation.pk
                lead.status = LeadStatus.NEGOTIATION
                lead.save(update_fields=['quotation_id', 'status'])
                QuotationLeadLink.objects.get_or_create(quotation=original_quotation, lead=lead)
                QuotationLeadLink.objects.get_or_create(quotation=new_quotation, lead=lead)

            # Step 5: Copy the ManyToMany relationship for terms.
            if original_terms:
                new_quotation.terms.set(original_terms)

            # Step 6: Duplicate the related ProductDetails (line items).
            new_details_to_create = []
            for detail in original_product_details:
                detail.pk = None
                detail.quotation = new_quotation
                new_details_to_create.append(detail)

            if new_details_to_create:
                ProductDetails.objects.bulk_create(new_details_to_create)

            ActivityLog.log(
                actor=request.user if request.user.is_authenticated else None,
                action=ActivityAction.QUOTATION_CREATED,
                entity=new_quotation,
                message=(
                    f"Quotation {new_quotation.quotation_number} revised from "
                    f"{original_quotation.quotation_number}"
                ),
                customer=new_quotation.customer,
            )

            return Response(
                {
                    "message": "Quotation revised successfully.",
                    "new_quotation_id": new_quotation.pk,
                    "lead_id": lead.pk if lead else None,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            # If any error occurs during the transaction, it will be rolled back.
            return Response(
                {"error": f"An unexpected error occurred during duplication: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

