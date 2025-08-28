# apps/quotations/email_service.py
import logging
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import EmailLog, EmailTemplate, Quotation

logger = logging.getLogger(__name__)

def send_quotation_email(quotation: Quotation):
    """
    A centralized service to send a quotation email to a customer.

    This function handles:
    - Finding the correct email template.
    - Replacing placeholders in the template with actual data.
    - Logging the email attempt.
    - Sending the email with the PDF link.
    - Updating the quotation and log status on success or failure.
    """
    if not (quotation and quotation.customer and quotation.customer.email):
        logger.warning(f"Quotation {quotation.id} cannot be sent: Missing customer or customer email.")
        return False, "Missing customer or customer email."

    # --- Create an initial log entry ---
    log_entry = EmailLog.objects.create(
        to_email=quotation.customer.email,
        subject=f"Quotation {quotation.quotation_number}",
        quotation=quotation,
        status='QUEUED'
    )

    try:
        template = quotation.email_template or EmailTemplate.objects.filter(is_default=True).first()
        if not template:
            raise ValueError("No default email template found.")
        subject = template.subject.replace("{{quotation_number}}", quotation.quotation_number)
        
        body = template.body_html
        replacements = {
            "{{customer_name}}": quotation.customer.name,
            "{{quotation_number}}": quotation.quotation_number,
            "{{total_amount}}": f"{quotation.currency} {quotation.total:,.2f}",
            "{{pdf_link}}": f'<a href="{quotation.file_url}" target="_blank">Download Quotation PDF</a>'
        }
        for placeholder, value in replacements.items():
            body = body.replace(placeholder, value)

        log_entry.subject = subject
        log_entry.body_preview = body[:500] # Save a preview
        
        # --- Send the Email ---
        send_mail(
            subject=subject,
            message="",  # Plain text version (optional)
            html_message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[quotation.customer.email],
            fail_silently=False,
        )

        # --- Update Status on Success ---
        quotation.status = 'SENT'
        quotation.emailed_at = timezone.now()
        quotation.save(update_fields=['status', 'emailed_at'])
        
        log_entry.mark_sent("Django-Mail") # Using a generic provider ID
        
        logger.info(f"Successfully sent quotation {quotation.quotation_number} to {quotation.customer.email}")
        return True, "Email sent successfully."

    except Exception as e:
        # --- Update Status on Failure ---
        error_message = f"Failed to send email: {str(e)}"
        logger.error(f"Error sending quotation {quotation.id}: {error_message}", exc_info=True)
        log_entry.mark_failed(error_message)
        return False, error_message