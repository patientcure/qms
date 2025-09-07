from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Quotation, ProductDetails, QuotationStatus, Lead, LeadStatus


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
        of both the quotation and its associated lead (if any), and saves them as new instances.
        """
        try:
            # Step 1: Retrieve the original quotation and its related items efficiently.
            original_quotation = get_object_or_404(
                Quotation.objects.prefetch_related('details', 'terms'), 
                pk=pk
            )
            original_product_details = list(original_quotation.details.all())
            original_terms = list(original_quotation.terms.all())

            # Step 2: Duplicate the associated lead, if it exists.
            new_lead_id = None
            if original_quotation.lead_id:
                try:
                    original_lead = Lead.objects.get(pk=original_quotation.lead_id)
                    new_lead = Lead(
                        customer=original_lead.customer,
                        assigned_to=original_lead.assigned_to,
                        lead_source=original_lead.lead_source,
                        priority=original_lead.priority,
                        follow_up_date=original_lead.follow_up_date,
                        notes=f"Duplicated from Lead ID: {original_lead.pk}.\n\n{original_lead.notes}",
                        status=LeadStatus.PENDING, # Reset status to default
                    )
                    new_lead.save()
                    new_lead_id = new_lead.pk
                except Lead.DoesNotExist:
                    # If the lead_id on the quotation is invalid, we proceed without a lead.
                    pass

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
                lead_id=new_lead_id,
                file_url= original_quotation.file_url,
            )
            new_quotation.save()

            # Step 4: If a new lead was created, link it back to the new quotation.
            if new_lead_id:
                Lead.objects.filter(pk=new_lead_id).update(quotation_id=new_quotation.pk)

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

            # Step 7: Return the ID of the newly created quotation.
            return Response(
                {"message": "Quotation and lead duplicated successfully.", "new_quotation_id": new_quotation.pk},
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            # If any error occurs during the transaction, it will be rolled back.
            return Response(
                {"error": f"An unexpected error occurred during duplication: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

