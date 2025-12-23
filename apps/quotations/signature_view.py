from .models import SignatureImage
from .forms import SignatureImageForm
from .views import JWTAuthMixin
from django.views.generic import View
from django.http import JsonResponse

class SignatureManageView(JWTAuthMixin, View):
    def post(self, request):
        form = SignatureImageForm(request.POST, request.FILES)

        if form.is_valid():
            signature_image = form.save(commit=False)
            signature_image.user = request.user
            signature_image.save()
            
            image_url = request.build_absolute_uri(signature_image.image.url)

            return JsonResponse({
                'success': True,
                'message': 'Signature uploaded successfully',
                'data': {
                    'id': signature_image.id,
                    'user_id': signature_image.user.id,
                    'image_url': image_url,
                    'uploaded_at': signature_image.created_at
                }
            }, status=201)
        else:
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)   
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
        
