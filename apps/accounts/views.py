from django.contrib.auth import authenticate, login, logout, get_user_model
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods
from django.utils.decorators import method_decorator
from django.views.generic import View
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.quotations.models import Quotation, ActivityAction, ActivityLog, QuotationStatus, Lead
from datetime import datetime
import json
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from apps.accounts.models import User,Roles
from apps.quotations.views import JWTAuthMixin,AdminRequiredMixin
class ProtectedView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return JsonResponse({
            'success': True,
            'message': f'Hello {request.user.username}, authenticated via JWT access token!'
        })

User = get_user_model()

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

@method_decorator(csrf_exempt, name='dispatch')
class BaseAPIView(View):
    """Base class for all API views with JSON parsing"""
    
    def dispatch(self, request, *args, **kwargs):
        if request.content_type == 'application/json' and request.body:
            try:
                request.json = json.loads(request.body)
            except json.JSONDecodeError:
                return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
        else:
            request.json = {}
        return super().dispatch(request, *args, **kwargs)


# ========== Authentication API ==========
class AdminLoginView(BaseAPIView):
    def post(self, request):
        username = request.json.get("username") or request.POST.get("username")
        password = request.json.get("password") or request.POST.get("password")
        
        if not username or not password:
            return JsonResponse({'success': False, 'error': 'Username and password are required'}, status=400)
        
        user = authenticate(request, username=username, password=password)
        if user and user.role == "ADMIN":
            tokens = get_tokens_for_user(user)
            return JsonResponse({
                'success': True,
                'message': 'Login successful',
                'tokens': tokens,
                'data': {
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'role': user.role,
                        'first_name': user.first_name,
                        'last_name': user.last_name
                    }
                }
            })
        else:
            return JsonResponse({'success': False, 'error': 'Invalid credentials or insufficient permissions'}, status=401)


class SalespersonLoginView(BaseAPIView):
    def post(self, request):
        username = request.json.get("username") or request.POST.get("username")
        password = request.json.get("password") or request.POST.get("password")

        if not username or not password:
            return JsonResponse({'success': False, 'error': 'Username and password are required'}, status=400)

        user = authenticate(request, username=username, password=password)
        if user and user.role == "SALESPERSON":
            tokens = get_tokens_for_user(user)
            return JsonResponse({
                'success': True,
                'message': 'Login successful',
                'tokens': tokens,
                'data': {
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'role': user.role,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'is_active': user.is_active
                    }
                }
            })
        else:
            return JsonResponse({'success': False, 'error': 'Invalid credentials or insufficient permissions'}, status=401)

#region Create
class CreateUserView(BaseAPIView):
    def post(self, request):
        data = request.json or request.POST
        username = data.get("username")
        email = data.get("email")
        password = data.get("password")
        role = data.get("role")
        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")
        phone_number=data.get("phone",None)
        address=data.get("address",None)
        if not all([username, email, password, role]):
            return JsonResponse({
                'success': False,
                'error': 'Username, email, password, and role are required'
            }, status=400)
        if role.upper() not in Roles.values:
            return JsonResponse({
                'success': False,
                'error': f"Invalid role. Choose from {', '.join(Roles.values)}"
            }, status=400)
        
        if User.objects.filter(username=username).exists():
            return JsonResponse({'success': False, 'error': 'Username already exists'}, status=400)
        
        if User.objects.filter(email=email).exists():
            return JsonResponse({'success': False, 'error': 'Email already exists'}, status=400)
        
        if phone_number and User.objects.filter(phone_number=phone_number).exists():
            return JsonResponse({'success': False, 'error': 'Phone number already exists'}, status=400)
        
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                role=role.upper(),
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                address=address
            )
            return JsonResponse({
                'success': True,
                'message': f'{user.get_role_display()} user created successfully',
                'data': {
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'role': user.role,
                        'phone_number':user.phone_number,
                        'address':user.address,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'is_active': user.is_active,
                        'date_joined': user.date_joined,
                    }
                }
            }, status=201)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Failed to create user: {str(e)}'
            }, status=400)
        
class DeleteUserView(APIView):
    def delete(self, request, user_id):
        print("Request user:", request.user)
        print("Role:", getattr(request.user, "role", None))
        if request.user.role != "ADMIN":

            return JsonResponse({
                'success': False,
                'error': 'Permission denied. Administrator access required.'
            }, status=403)
        
        user = get_object_or_404(User, pk=user_id)
        
        user.delete()
        return JsonResponse({
            'success': True,
            'message': f'User {user.username} deleted successfully'
        })

class UserListView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != "ADMIN":
            return JsonResponse({
                'success': False,
                'error': 'Permission denied. Administrator access required.'
            }, status=403)
        
        users = User.objects.all().order_by('first_name', 'last_name')        
        data = [{
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'phone_number':user.phone_number,
            'address':user.address,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'is_active': user.is_active,
            'date_joined': user.date_joined
        } for user in users]

        return JsonResponse({'success': True, 'data': data})


class LogoutView(BaseAPIView):
    def post(self, request):
        try:
            refresh_token = request.json.get("refresh")
            token = RefreshToken(refresh_token)
            token.blacklist()
            return JsonResponse({'success': True, 'message': 'Logged out successfully'})
        except Exception:
            return JsonResponse({'success': False, 'error': 'Invalid refresh token'}, status=400)


class CurrentUserView(JWTAuthMixin, View):
    def get(self, request):
        user = request.user
        return JsonResponse({
            'success': True,
            'data': {
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'phone_number':user.phone_number,
                    'is_active': user.is_active,
                    'date_joined': user.date_joined,
                    'address' : user.address,
                }
            }
        })

class CheckTokenValidityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return JsonResponse({
            'success': True,
            'message': 'Access token is valid.',
            'user': {
                'id': request.user.id,
                'username': request.user.username,
                'email': request.user.email,
                'role': request.user.role,
            }
        })


# ========== Password Management API ==========
class ChangePasswordView(APIView):
    """
    An endpoint for changing password.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = self.request.user
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")

        if not old_password or not new_password:
            return JsonResponse({
                'success': False, 
                'error': 'Old password and new password are required.'
            }, status=400)

        # Check old password
        if not user.check_password(old_password):
            return JsonResponse({
                'success': False, 
                'error': 'Your old password was entered incorrectly. Please enter it again.'
            }, status=400)
        
        # validate password
        if len(new_password) < 6:
             return JsonResponse({
                'success': False,
                'error': 'Password must be at least 8 characters long.'
            }, status=400)


        # set_password also hashes the password that the user will get
        user.set_password(new_password)
        user.save()
        return JsonResponse({'success': True, 'message': 'Password updated successfully'})


# ========== Quotation Status Update API ==========
class QuotationStatusUpdateView(JWTAuthMixin, BaseAPIView):
    def put(self, request, quotation_id):
        quotation = get_object_or_404(Quotation, pk=quotation_id)
        

        changes = []
        
        status = request.json.get("status")
        if status and status in dict(QuotationStatus.choices) and status != quotation.status:
            old_status = quotation.status
            quotation.status = status
            changes.append(f"Status changed from {old_status} to {status}")
        
        follow_up_date_str = request.json.get("follow_up_date")
        if follow_up_date_str:
            try:
                new_date = datetime.strptime(follow_up_date_str, "%Y-%m-%d").date()
                if quotation.follow_up_date != new_date:
                    old_date = quotation.follow_up_date
                    quotation.follow_up_date = new_date
                    changes.append(f"Follow-up date changed from {old_date} to {new_date}")
            except ValueError:
                return JsonResponse({'success': False, 'error': 'Invalid follow-up date format. Use YYYY-MM-DD.'}, status=400)
        
        if changes:
            quotation.save(update_fields=['status', 'follow_up_date'])
            message = "; ".join(changes)
            ActivityLog.log(
                actor=request.user,
                action=ActivityAction.QUOTATION_UPDATED,
                entity=quotation,
                message=message,
                customer=quotation.customer,
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Quotation updated successfully',
                'data': {
                    'id': quotation.id,
                    'status': quotation.status,
                    'follow_up_date': quotation.follow_up_date.isoformat() if quotation.follow_up_date else None,
                    'changes': changes
                }
            })
        else:
            return JsonResponse({
                'success': True,
                'message': 'No changes made',
                'data': {
                    'id': quotation.id,
                    'status': quotation.status,
                    'follow_up_date': quotation.follow_up_date.isoformat() if quotation.follow_up_date else None
                }
            })


# ========== Lead Status Update API ==========
import traceback

class LeadStatusUpdateView(JWTAuthMixin,BaseAPIView):
    def put(self, request, lead_id):
        try:
            lead = get_object_or_404(Lead, pk=lead_id)

            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                return JsonResponse({'success': False, 'error': 'Invalid JSON.'}, status=400)

            changes = []
            fields_to_update = []

            status = data.get("status")
            if status and status != lead.status:
                old_status = lead.status
                lead.status = status
                changes.append(f"Status changed from {old_status} to {status}")
                fields_to_update.append('status')

            follow_up_date_str = data.get("follow_up_date")
            if follow_up_date_str:
                try:
                    new_date = datetime.strptime(follow_up_date_str, "%Y-%m-%d").date()
                    if lead.follow_up_date != new_date:
                        old_date = lead.follow_up_date
                        lead.follow_up_date = new_date
                        changes.append(f"Follow-up date changed from {old_date} to {new_date}")
                        fields_to_update.append('follow_up_date')
                except ValueError:
                    return JsonResponse({'success': False, 'error': 'Invalid follow-up date format. Use YYYY-MM-DD.'}, status=400)
            elif follow_up_date_str == "":
                if lead.follow_up_date:
                    old_date = lead.follow_up_date
                    lead.follow_up_date = None
                    changes.append(f"Follow-up date removed (was {old_date})")
                    fields_to_update.append('follow_up_date')

            if fields_to_update:
                lead.save(update_fields=fields_to_update)
                try:
                    ActivityLog.log(
                        actor=request.user,
                        action=ActivityAction.LEAD_UPDATED,
                        entity=lead,
                        message="; ".join(changes),
                        customer = lead.customer,
                    )
                except Exception as e:
                    return JsonResponse({'success': False, 'error': f'Activity log failed: {str(e)}'}, status=500)

                return JsonResponse({
                    'success': True,
                    'message': 'Lead updated successfully',
                    'data': {
                        'id': lead.id,
                        'status': lead.status,
                        'follow_up_date': lead.follow_up_date.isoformat() if lead.follow_up_date else None,
                        'changes': changes
                    }
                })

            return JsonResponse({
                'success': True,
                'message': 'No changes made',
                'data': {
                    'id': lead.id,
                    'status': lead.status,
                    'follow_up_date': lead.follow_up_date.isoformat() if lead.follow_up_date else None
                }
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }, status=500)


class ToggleUserType(AdminRequiredMixin, BaseAPIView):
    def post(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        if user.role == "ADMIN":
            user.role = "SALESPERSON"
        elif user.role == "SALESPERSON":
            user.role = "ADMIN"
        else:
            return JsonResponse({
                'success': False,
                'error': 'Only ADMIN and SALESPERSON roles can be toggled.'
            }, status=400)
        user.save(update_fields=['role'])
        return JsonResponse({
            'success': True,
            'message': f'User role toggled to {user.role}',
            'data': {
                'id': user.id,
                'username': user.first_name,
                'role': user.role
            }
        })

class EditUserView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        # Only allow admin or the user themselves to edit
        if request.user.role != "ADMIN" and request.user.id != user.id:
            return JsonResponse({
                'success': False,
                'error': 'Permission denied. Only admin or the user themselves can edit.'
            }, status=403)

        data = request.json if hasattr(request, 'json') else request.data
        # Update allowed fields
        allowed_fields = [
            'first_name', 'last_name', 'email', 'address', 'phone_number', 'username'
        ]
        updated = False
        for field in allowed_fields:
            if field in data and getattr(user, field, None) != data[field]:
                setattr(user, field, data[field])
                updated = True
        if updated:
            user.save()
            return JsonResponse({
                'success': True,
                'message': 'User details updated successfully',
                'data': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role,
                    'phone_number': user.phone_number,
                    'address': user.address,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_active': user.is_active,
                    'date_joined': user.date_joined,
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'No changes detected.'
            }, status=400)
