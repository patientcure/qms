from .pdf_service import QuotationPDFGenerator
import os
from django.conf import settings
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def save_quotation_pdf(quotation, request=None, terms=None):
    try:
        from .models import CompanyProfile
        company = CompanyProfile.objects.first()
        
        generator = QuotationPDFGenerator(quotation, company, terms=terms)
        pdf_content = generator.generate()
        
        pdf_dir = os.path.join(settings.MEDIA_ROOT, 'quotations')
        os.makedirs(pdf_dir, exist_ok=True)
        
        filename = f"quotation_{quotation.quotation_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(pdf_dir, filename)
        
        with open(filepath, 'wb') as f:
            f.write(pdf_content)
        
        relative_path = os.path.relpath(filepath, settings.MEDIA_ROOT)
        relative_path = relative_path.replace(os.sep, '/')
        
        media_url = settings.MEDIA_URL.rstrip('/')
        pdf_relative_url = f"{media_url}/{relative_path}"
        
        if request:
            pdf_url = request.build_absolute_uri(pdf_relative_url)
        else:
            pdf_url = pdf_relative_url
        
        return filepath, pdf_url
        
    except Exception as e:
        logger.error(f"Error generating PDF for quotation {quotation.id}: {str(e)}")
        raise Exception(f"Failed to generate PDF: {str(e)}")

def save_quotation_pdf_with_terms(quotation, terms_list, request=None):
    if isinstance(terms_list, str):
        terms = [int(t.strip()) for t in terms_list.split(',') if t.strip().isdigit()]
    elif isinstance(terms_list, list):
        terms = [int(t) for t in terms_list if str(t).strip()]
    else:
        terms = []
    
    return save_quotation_pdf(quotation, request, terms=terms)