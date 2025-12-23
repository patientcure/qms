from .models import SignatureImage
from .forms import SignatureImageForm
from .views import JWTAuthMixin
from django.views.generic import View
from django.http import JsonResponse

class SignatureManageView(JWTAuthMixin, View):
    def post(self, request):
        try:
            if 'image' not in request.FILES:
                return JsonResponse({
                    'success': False, 
                    'message': 'No image file was found in the request.'
                }, status=400)

            image_file = request.FILES['image']
            signature_image = SignatureImage.objects.create(
                user=request.user,
                image=image_file
            )
            image_url = request.build_absolute_uri(signature_image.image.url)
            return JsonResponse({
                'success': True,
                'message': 'Signature uploaded successfully',
                'data': {
                    'id': signature_image.id,
                    'user_id': signature_image.user.id,
                    'image_url': image_url,
                    'uploaded_at': signature_image.created_at.isoformat() 
                }
            }, status=201)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': 'A server error occurred during the upload process.',
                'error_type': e.__class__.__name__,
                'error_detail': str(e)
            }, status=500)
        
    def get(self, request):
        user = request.user
        try:
            signature_image = SignatureImage.objects.get(user=user)
            image_url = request.build_absolute_uri(signature_image.image.url)

            return JsonResponse({
                'success': True,
                'data': {
                    'id': signature_image.id,
                    'user_id': signature_image.user.id,
                    'image_url': image_url,
                    'uploaded_at': signature_image.created_at
                }
            }, status=200)
        except SignatureImage.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'No signature found for this user.'}, status=404)
    def delete(self, request):
        user = request.user
        try:
            signature_image = SignatureImage.objects.get(user=user)
            signature_image.delete()
            return JsonResponse({'success': True, 'message': 'Signature deleted successfully.'}, status=200)
        except SignatureImage.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'No signature found for this user.'}, status=404)
        
