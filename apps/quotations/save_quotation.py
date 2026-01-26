import os
from django.conf import settings
import logging
from datetime import datetime
from .models import CompanyProfile, Product
from .pdf_service import QuotationPDFGenerator

logger = logging.getLogger(__name__)

def save_quotation_pdf(quotation, request, items_data, terms=None):
    try:
        product_ids = [item.get('product') for item in items_data if item.get('product')]
        products = {p.id: p for p in Product.objects.filter(id__in=product_ids)}

        enriched_items = []
        for item in items_data:
            product = products.get(int(item.get('product')))
            if not product:
                continue

            unit_price = item.get('unit_price') or product.selling_price
            enriched_items.append({
                'product': {'id': product.id, 'name': product.name},
                'quantity': item.get('quantity', 1),
                'unit_price': str(unit_price),
                'description': item.get('description', product.name),
                'discount': item.get('discount', 0),
                # FIX: Use the local file system path instead of a URL
                'image_path': product.image.path if product.image else None
            })

        company_profile = CompanyProfile.objects.first()

        # FIX: Use local path for signature
        signature_path = None
        if hasattr(request.user, 'signature') and request.user.signature and request.user.signature.image:
            signature_path = request.user.signature.image.path
        
        generator = QuotationPDFGenerator(
            user=request.user,
            quotation=quotation,
            items_data=enriched_items,
            company_profile=company_profile,
            terms=terms,
            signature=signature_path
        )
        pdf_content = generator.generate()

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_name = f'quotation_{quotation.quotation_number}_{timestamp}.pdf'
        file_path = os.path.join(settings.MEDIA_ROOT, 'quotations', file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, 'wb') as f:
            f.write(pdf_content)

        pdf_url = request.build_absolute_uri(os.path.join(settings.MEDIA_URL, 'quotations', file_name))
        return file_path, pdf_url

    except Exception as e:
        logger.error(f"Error generating PDF: {e}", exc_info=True)
        raise