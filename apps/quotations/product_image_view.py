from .models import ProductImage
from .forms import ProductImageForm
from .views import JWTAuthMixin 
from django.views.generic import View
from django.http import JsonResponse


class ProductImageUploadView(JWTAuthMixin, View):
    def post(self, request):
        form = ProductImageForm(request.POST, request.FILES)

        if form.is_valid():
            product_image = form.save()
            
            image_url = request.build_absolute_uri(product_image.image.url)

            return JsonResponse({
                'success': True,
                'message': 'Image uploaded successfully',
                'data': {
                    'id': product_image.id,
                    'product_id': product_image.product.id,
                    'quotation_id': product_image.quotation.id if product_image.quotation else None,
                    'image_url': image_url,
                    'uploaded_at': product_image.created_at
                }
            }, status=201)
        else:
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)