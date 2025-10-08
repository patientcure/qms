# apps/quotations/email_service.py
import logging
from urllib.request import urlopen

from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils import timezone

from .models import EmailLog, Quotation
from .email_template import mytemplate

logger = logging.getLogger(__name__)


def send_quotation_email(quotation: Quotation):
    if not (quotation and quotation.customer and quotation.customer.email):
        logger.warning(
            f"[Quotation {getattr(quotation, 'id', 'N/A')}] Missing customer or customer email."
        )
        return False, "Missing customer or customer email."

    # --- Create initial log entry ---
    log_entry = EmailLog.objects.create(
        to_email=quotation.customer.email,
        subject=f"Quotation {quotation.quotation_number}",
        quotation=quotation,
        status="QUEUED",
    )

    try:
        # --- Generate professional template ---
        subject, plain_text, html_content = mytemplate(quotation)

        log_entry.subject = subject
        log_entry.body_preview = plain_text[:500]

        # --- Build email with plain + HTML ---
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            # to=[quotation.customer.email],
            to = "naman@nkprosales.com"
        )

        try:
            email.attach_alternative(html_content, "text/html")
        except Exception as e:
            logger.error(
                f"[Quotation {quotation.quotation_number}] Failed to attach HTML body: {e}"
            )
            # fallback: plain text only
            pass

        # --- Attach PDF ---
        if quotation.has_pdf and quotation.file_url:
            try:
                pdf_content = urlopen(quotation.file_url).read()
                email.attach(
                    f"Quotation_{quotation.quotation_number}.pdf",
                    pdf_content,
                    "application/pdf",
                )
            except Exception as e:
                logger.error(
                    f"[Quotation {quotation.quotation_number}] Failed to fetch/attach PDF: {e}"
                )
                # Do not block sending — just skip PDF

        # --- Send email ---
        email.send(fail_silently=False)

        # --- Update quotation status ---
        quotation.status = "SENT"
        quotation.emailed_at = timezone.now()
        quotation.save(update_fields=["status", "emailed_at"])

        log_entry.mark_sent("Django-Mail")

        logger.info(
            f"[Quotation {quotation.quotation_number}] Sent successfully to {quotation.customer.email}"
        )
        return True, "Email sent successfully."

    except Exception as e:
        error_message = f"Failed to send email: {str(e)}"
        logger.error(
            f"[Quotation {getattr(quotation, 'quotation_number', 'N/A')}] {error_message}",
            exc_info=True,
        )
        log_entry.mark_failed(error_message)
        return False, error_message
