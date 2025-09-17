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
            enriched_items.append({
                'product': {'id': product.id, 'name': product.name},
                'quantity': item.get('quantity', 1),
                'unit_price': str(unit_price),
                'description': item.get('description', product.name),
                'discount': item.get('discount', 0),
            })

        company_profile = CompanyProfile.objects.first()

        # --- Generate PDF ---
        generator = QuotationPDFGenerator(
            quotation=quotation,
            items_data=enriched_items,
            company_profile=company_profile,
            terms=terms
        )
        pdf_content = generator.generate()

        # --- File path ---
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_name = f'quotation_{quotation.quotation_number}_{timestamp}.pdf'
        file_path = os.path.join(settings.GENERATED_FILES_DIR, file_name)

        # --- Save PDF locally ---
        with open(file_path, 'wb') as f:
            f.write(pdf_content)

        # --- Generate public URL ---
        pdf_url = request.build_absolute_uri(os.path.join(settings.STATIC_URL, 'quotations', file_name))

        logger.info(f"PDF saved locally for quotation {quotation.id}. URL: {pdf_url}")
        return file_path, pdf_url

    except Exception as e:
        logger.error(f"Error generating PDF for quotation {quotation.id}: {e}", exc_info=True)
        raise