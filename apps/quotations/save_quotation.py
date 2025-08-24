from .pdf_service import QuotationPDFGenerator

def save_quotation_pdf(quotation, request=None, terms=None):
    """
    Generate and save quotation PDF, return file path and URL
    
    Args:
        quotation: Quotation instance
        request: HTTP request object (optional)
        terms: List of term IDs to include in PDF (optional)
    
    Returns:
        tuple: (filepath, pdf_url)
    """
    from .models import CompanyProfile
    import os
    from django.conf import settings
    from datetime import datetime
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # Get company profile
        company = CompanyProfile.objects.first()
        
        # Generate PDF with terms parameter
        generator = QuotationPDFGenerator(quotation, company, terms=terms)
        pdf_content = generator.generate()
        
        # Create directory if it doesn't exist
        pdf_dir = os.path.join(settings.MEDIA_ROOT, 'quotations')
        os.makedirs(pdf_dir, exist_ok=True)
        
        # Generate filename
        filename = f"quotation_{quotation.quotation_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(pdf_dir, filename)
        
        # Save PDF file
        with open(filepath, 'wb') as f:
            f.write(pdf_content)
        
        # FIXED: Proper URL construction
        # Use os.path.relpath to get the relative path properly
        relative_path = os.path.relpath(filepath, settings.MEDIA_ROOT)
        
        # Ensure forward slashes for URLs (important for Windows compatibility)
        relative_path = relative_path.replace(os.sep, '/')
        
        # Construct the media URL properly
        media_url = settings.MEDIA_URL.rstrip('/')  # Remove trailing slash if present
        pdf_relative_url = f"{media_url}/{relative_path}"
        
        if request:
            pdf_url = request.build_absolute_uri(pdf_relative_url)
        else:
            # For cases where request is not available
            pdf_url = pdf_relative_url
        
        logger.info(f"PDF generated successfully for quotation {quotation.quotation_number}")
        if terms:
            logger.info(f"Included {len(terms)} terms in PDF")
        
        return filepath, pdf_url
        
    except Exception as e:
        logger.error(f"Error generating PDF for quotation {quotation.id}: {str(e)}")
        raise Exception(f"Failed to generate PDF: {str(e)}")


def save_quotation_pdf_with_terms(quotation, terms_list, request=None):
    """
    Convenience function to generate PDF with specific terms
    
    Args:
        quotation: Quotation instance
        terms_list: List of term IDs or comma-separated string
        request: HTTP request object (optional)
    
    Returns:
        tuple: (filepath, pdf_url)
    """
    # Handle different term formats
    if isinstance(terms_list, str):
        # Handle comma-separated string
        terms = [int(t.strip()) for t in terms_list.split(',') if t.strip().isdigit()]
    elif isinstance(terms_list, list):
        # Handle list of IDs
        terms = [int(t) for t in terms_list if str(t).strip()]
    else:
        terms = []
    
    return save_quotation_pdf(quotation, request, terms=terms)