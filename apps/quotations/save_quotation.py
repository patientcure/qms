
import os
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from decimal import Decimal
import logging
from .models import CompanyProfile, Product
from .pdf_service import QuotationPDFGenerator
from datetime import datetime

logger = logging.getLogger(__name__)

def save_quotation_pdf(quotation, request, items_data, terms=None):
    try:
        product_ids = [item.get('product') for item in items_data if item.get('product')]
        products = {p.id: p for p in Product.objects.filter(id__in=product_ids)}
        
        enriched_items = []
        for item in items_data:
            product = products.get(item.get('product'))
            if not product:
                logger.warning(f"Product ID {item.get('product')} not found for quotation {quotation.id}")
                continue
            unit_price = item.get('unit_price') or product.selling_price
            tax_rate = item.get('tax_rate') or product.tax_rate
            
            enriched_item = {
                'product': {'id': product.id, 'name': product.name},
                'quantity': item.get('quantity', 1),
                'unit_price': str(unit_price),
                'tax_rate': str(tax_rate),
                'description': item.get('description', product.name),
                'discount': item.get('discount', 0)
            }
            enriched_items.append(enriched_item)
        company_profile = CompanyProfile.objects.first()
        generator = QuotationPDFGenerator(
            quotation=quotation,
            items_data=enriched_items,  # <-- Pass the corrected item data
            company_profile=company_profile,
            terms=terms
        )
        pdf_content = generator.generate()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_name = f'quotation_{quotation.quotation_number}_{timestamp}.pdf'
        file_path = os.path.join('quotations', file_name)
        if default_storage.exists(file_path):
            default_storage.delete(file_path)
        
        saved_path = default_storage.save(file_path, ContentFile(pdf_content))
        
        if request:
            pdf_url = request.build_absolute_uri(default_storage.url(saved_path))
        else:
            pdf_url = default_storage.url(saved_path)

        logger.info(f"Successfully generated PDF for quotation {quotation.id} at {pdf_url}")
        return saved_path, pdf_url
        
    except Exception as e:
        logger.error(f"Error generating PDF for quotation {quotation.id}", exc_info=True)
        raise Exception(f"Failed to generate PDF: {str(e)}")
