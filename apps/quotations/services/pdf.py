from django.template.loader import render_to_string
from django.conf import settings
from pathlib import Path
from weasyprint import HTML
import tempfile

from apps.quotations.models import CompanyProfile


def render_quotation_pdf(quotation) -> str:
    """Render PDF and return local file path (temporary)."""
    context = {
        'quotation': quotation,
        'company': CompanyProfile.objects.first(),
        'items': quotation.items.select_related('product').all(),
    }
    html = render_to_string('pdf/quotation.html', context)
    tmpdir = tempfile.mkdtemp(prefix='qms_pdf_')
    pdf_path = str(Path(tmpdir) / f"{quotation.quotation_number}.pdf")
    HTML(string=html, base_url=str(Path(settings.BASE_DIR))).write_pdf(pdf_path)
    return pdf_path
