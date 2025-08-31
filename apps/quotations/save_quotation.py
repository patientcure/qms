import os
from django.conf import settings
from django.core.files.base import ContentFile
from decimal import Decimal
import logging
from datetime import datetime
from .models import CompanyProfile, Product
from .pdf_service import QuotationPDFGenerator
from storages.backends.gcloud import GoogleCloudStorage

logger = logging.getLogger(__name__)

def save_quotation_pdf(quotation, request, items_data, terms=None):
    """
    Generates a PDF for a quotation and saves it explicitly to Firebase Storage.
    Returns the storage path and the public Firebase URL.
    """
    try:
        product_ids = [item.get('product') for item in items_data if item.get('product')]
        products = {p.id: p for p in Product.objects.filter(id__in=product_ids)}
        
        enriched_items = []
        for item in items_data:
            product = products.get(int(item.get('product'))) 
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

        # --- PDF Generation ---
        generator = QuotationPDFGenerator(
            quotation=quotation,
            items_data=enriched_items,
            company_profile=company_profile,
            terms=terms
        )
        pdf_content = generator.generate()

        # --- Saving to explicit storage ---
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_name = f'quotation_{quotation.quotation_number}_{timestamp}.pdf'
        file_path = os.path.join('quotations', file_name)
        
        # --- 2. CREATE AN EXPLICIT INSTANCE OF THE STORAGE BACKEND ---
        gcs_storage = GoogleCloudStorage()

        # --- 3. USE THE EXPLICIT INSTANCE INSTEAD OF default_storage ---
        saved_path = gcs_storage.save(file_path, ContentFile(pdf_content))
        pdf_url = gcs_storage.url(saved_path)

        logger.info(f"Successfully uploaded PDF for quotation {quotation.id}. URL: {pdf_url}")
        
        return saved_path, pdf_url
        
    except Product.DoesNotExist:
        logger.error(f"A product listed in the quotation's items does not exist.")
        raise Exception("One or more products in the quotation could not be found.")
    except Exception as e:
        logger.error(f"An unexpected error occurred while generating PDF for quotation {quotation.id}: {e}", exc_info=True)
        raise