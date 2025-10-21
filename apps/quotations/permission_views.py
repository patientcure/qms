from .models import SalespersonPermission
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from apps.accounts.models import User, Roles
from .views import AdminRequiredMixin, JWTAuthMixin, BaseAPIView 
from .permissions import PERMISSIONS_MAP


class AdminManagePermissionsView(AdminRequiredMixin, BaseAPIView):
    def get(self, request, user_id):
        salesperson = get_object_or_404(User, pk=user_id, role=Roles.SALESPERSON)
        permissions_obj, _ = SalespersonPermission.objects.get_or_create(user=salesperson)
        return JsonResponse({'success': True, 'data': permissions_obj.permissions})

    def put(self, request, user_id):
        salesperson = get_object_or_404(User, pk=user_id, role=Roles.SALESPERSON)
        permissions_data = request.json
        
        if not isinstance(permissions_data, dict):
            return JsonResponse({'success': False, 'error': 'Invalid data format. Must be a JSON object.'}, status=400)

        permissions_obj, _ = SalespersonPermission.objects.update_or_create(
            user=salesperson,
            defaults={'permissions': permissions_data}
        )
        return JsonResponse({
            'success': True, 
            'message': f'Permissions for {salesperson.get_full_name()} updated successfully.',
            'data': permissions_obj.permissions
        })


class MyPermissionsView(JWTAuthMixin, BaseAPIView):

    def get(self, request):
        user = request.user
        
        response_data = {
            'system_permissions': PERMISSIONS_MAP
        }

        if user.role == Roles.ADMIN:
            admin_perms = {entity: actions for entity, actions in PERMISSIONS_MAP.items()}
            response_data['user_permissions'] = admin_perms
            response_data['role'] = user.role
        
        elif user.role == Roles.SALESPERSON:
            permissions_obj, _ = SalespersonPermission.objects.get_or_create(user=user)
            response_data['user_permissions'] = permissions_obj.permissions
            response_data['role'] = user.role
        
        else:
            response_data['user_permissions'] = {}
            response_data['role'] = user.role

        return JsonResponse({'success': True, 'data': response_data})