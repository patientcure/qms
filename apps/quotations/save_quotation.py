from .pdf_service import QuotationPDFGenerator

def save_quotation_pdf(quotation, request=None):
    """
    Generate and save quotation PDF, return file path and URL
    """
    from .models import CompanyProfile
    import os
    from django.conf import settings
    from datetime import datetime
    
    # Get company profile
    company = CompanyProfile.objects.first()
    
    # Generate PDF
    generator = QuotationPDFGenerator(quotation, company)
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
    
    return filepath, pdf_url