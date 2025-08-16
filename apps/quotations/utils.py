from django.conf import settings
from django.db import transaction
from django.utils import timezone

@transaction.atomic
def generate_next_quotation_number() -> str:
    from .models import Quotation
    prefix = getattr(settings, 'QUOTATION_PREFIX', 'QTN')
    year = timezone.localdate().strftime('%Y')
    base = f"{prefix}-{year}-"
    # Lock the table slice for this year to avoid race conditions
    last = (
        Quotation.objects.select_for_update()
        .filter(quotation_number__startswith=base)
        .order_by('-quotation_number')
        .first()
    )
    if last:
        last_seq = int(last.quotation_number.split('-')[-1])
    else:
        last_seq = 0
    next_seq = str(last_seq + 1).zfill(4)
    return f"{base}{next_seq}"

def send_and_archive_quotation(quotation):
    """
    Generate PDF, send via SendGrid, upload to Drive, update status & log activity.
    """
    # TODO: Implement actual PDF generation, SendGrid, Google Drive upload
    print(f"Sending quotation {quotation.quotation_number} to {quotation.customer.email}")
    quotation.status = "MAIL_SENT"
    quotation.emailed_at = timezone.now()
    quotation.save()
    # Log in EmailLog or ActivityLog if needed
    return True
