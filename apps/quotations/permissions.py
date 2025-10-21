from functools import wraps
from django.http import JsonResponse
from apps.accounts.models import Roles

PERMISSIONS_MAP = {
    'quotation': ['edit', 'delete'],
    'lead': ['edit', 'delete'],
    'customer': ['edit', 'delete'],
    'product': [ 'edit', 'delete'],
    'terms' : ['edit', 'delete'],
}

def check_permissions_in_url(view_func, entity: str, permission_map: dict):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        user = request.user
        action = permission_map.get(request.method)
        if not action:
            return view_func(request, *args, **kwargs)

        if user.role == Roles.ADMIN:
            return view_func(request, *args, **kwargs)

        if user.role == Roles.SALESPERSON:
            try:
                user_permissions = user.permissions.permissions
                allowed_actions = user_permissions.get(entity, [])
                if action in allowed_actions:
                    return view_func(request, *args, **kwargs)
            except AttributeError:
                pass

        return JsonResponse({
            'success': False,
            'error': f'Permission denied. You do not have permission to {action} {entity}s.'
        }, status=403)
        
    return _wrapped_view