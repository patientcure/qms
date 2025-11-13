import os
import json
import logging
from datetime import datetime

from django.core.files.base import ContentFile
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from .views import BaseAPIView, JWTAuthMixin
from .models import CompanyProfile, Product, Category
from .forms import ProductForm
from django.db.models import ProtectedError

logger = logging.getLogger(__name__)


class ProductCreateView(BaseAPIView):
    def _parse_request_data(self, request):
        if request.content_type == 'application/json':
            try:
                body = request.body.decode('utf-8') if request.body else ''
                return json.loads(body) if body else {}
            except json.JSONDecodeError:
                return None
            except Exception:
                return None

        try:
            return request.POST.copy()
        except Exception:
            return None

    def _handle_category(self, data):
        try:
            category_data = data.get('category')
            if category_data and isinstance(category_data, str):
                category = Category.objects.filter(name__iexact=category_data).first()
                if not category:
                    category = Category.objects.create(name=category_data)
                data['category'] = category.pk
        except Exception:
            pass
        return data

    def _handle_image_upload(self, product, request):
        try:
            if not hasattr(request, 'FILES') or not request.FILES:
                return False

            image_file = request.FILES.get('image')

            if not image_file and 'images' in request.FILES:
                try:
                    files_list = request.FILES.getlist('images')
                    if files_list:
                        image_file = files_list[0]
                except Exception:
                    image_file = request.FILES.get('images')

            if not image_file:
                return False

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            original_name = getattr(image_file, 'name', 'uploaded')
            _, ext = os.path.splitext(original_name)
            safe_name = f"product_{product.id}_{timestamp}{ext or ''}"
            relative_path = os.path.join(str(product.id), safe_name)

            file_content = ContentFile(image_file.read())
            product.image.save(relative_path, file_content, save=True)

            return True
        except Exception:
            return False

    @transaction.atomic
    def post(self, request):
        try:
            data = self._parse_request_data(request)
            if data is None:
                return JsonResponse({'error': 'Invalid JSON or Form Data'}, status=400)

            product_id = data.get('id')

            if product_id:
                product = get_object_or_404(Product, pk=product_id)
                form = ProductForm(data, instance=product)
            else:
                form = ProductForm(data)

            data = self._handle_category(data)

            if form.is_valid():
                if product_id:
                    update_fields = [f for f in data.keys() if f in form.cleaned_data]
                    if 'category' in data and 'category' not in update_fields:
                        update_fields.append('category')

                    product = form.save(commit=False)
                    product.save(update_fields=update_fields)
                    message = 'Product updated successfully'
                else:
                    product = form.save()
                    message = 'Product created successfully'

                if hasattr(request, 'FILES') and request.FILES:
                    self._handle_image_upload(product, request)

                image_url = None
                if product.image:
                    try:
                        image_url = request.build_absolute_uri(product.image.url)
                    except Exception:
                        pass

                return JsonResponse({
                    'success': True,
                    'message': message,
                    'data': {
                        'id': product.id,
                        'name': product.name,
                        'category': product.category.name if product.category else None,
                        'cost_price': float(product.cost_price or 0),
                        'selling_price': float(product.selling_price or 0),
                        'unit': product.unit,
                        'image': image_url
                    }
                }, status=201 if not product_id else 200)
            else:
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)

        except Exception:
            logger.exception("Unhandled exception in ProductCreateView.post")
            return JsonResponse({'error': 'Internal server error'}, status=500)

    def put(self, request):
        return JsonResponse({'error': 'Please use POST method for file updates.'}, status=405)
    def delete(self, request):
        """Handles the permanent deletion of a product."""
        product_id = request.GET.get('id')
        if not product_id:
            return JsonResponse({'error': 'Product ID is required.'}, status=400)

        try:
            # Use .get() to catch DoesNotExist separately
            product = Product.objects.get(pk=product_id)
            product_id_to_confirm = product.id
            product.delete()
            return JsonResponse({
                'success': True,
                'message': f'Product with ID {product_id_to_confirm} has been permanently deleted.',
            })
        except Product.DoesNotExist:
            return JsonResponse({'error': f'Product with ID {product_id} not found.'}, status=404)
        except ProtectedError:
            return JsonResponse({
                'error': f'Product with ID {product_id} cannot be deleted because it is being used in one or more quotations.'
            }, status=409) # 409 Conflict is appropriate here
        except Exception as e:
            # Catch any other unexpected database errors
            return JsonResponse({'error': f'An unexpected error occurred: {str(e)}'}, status=500)
