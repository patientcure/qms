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

User = get_user_model()


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
            return JsonResponse({
                'success': False, 
                'error': 'Username and password are required'
            }, status=400)
        
        user = authenticate(request, username=username, password=password)
        if user and user.role == "ADMIN":
            login(request, user)
            return JsonResponse({
                'success': True,
                'message': 'Login successful',
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
            return JsonResponse({
                'success': False, 
                'error': 'Invalid credentials or insufficient permissions'
            }, status=401)


class SalespersonLoginView(BaseAPIView):
    def post(self, request):
        username = request.json.get("username") or request.POST.get("username")
        password = request.json.get("password") or request.POST.get("password")
        
        if not username or not password:
            return JsonResponse({
                'success': False, 
                'error': 'Username and password are required'
            }, status=400)
        
        user = authenticate(request, username=username, password=password)
        if user and user.role == "SALESPERSON":
            login(request, user)
            return JsonResponse({
                'success': True,
                'message': 'Login successful',
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
            return JsonResponse({
                'success': False, 
                'error': 'Invalid credentials or insufficient permissions'
            }, status=401)


class CreateAdminView(BaseAPIView):
    def post(self, request):
        # Optional: Check if admin already exists
        # if User.objects.filter(role="ADMIN").exists():
        #     return JsonResponse({
        #         'success': False, 
        #         'error': 'Admin already exists'
        #     }, status=400)
        
        username = request.json.get("username") or request.POST.get("username")
        email = request.json.get("email") or request.POST.get("email")
        password = request.json.get("password") or request.POST.get("password")
        first_name = request.json.get("first_name") or request.POST.get("first_name", "")
        last_name = request.json.get("last_name") or request.POST.get("last_name", "")
        
        if not all([username, email, password]):
            return JsonResponse({
                'success': False, 
                'error': 'Username, email, and password are required'
            }, status=400)
        
        # Check if username already exists
        if User.objects.filter(username=username).exists():
            return JsonResponse({
                'success': False, 
                'error': 'Username already exists'
            }, status=400)
        
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            return JsonResponse({
                'success': False, 
                'error': 'Email already exists'
            }, status=400)
        
        try:
            user = User.objects.create_user(
                username=username, 
                email=email, 
                password=password, 
                role="ADMIN",
                first_name=first_name,
                last_name=last_name
            )
            return JsonResponse({
                'success': True,
                'message': 'Admin created successfully',
                'data': {
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'role': user.role
                    }
                }
            }, status=201)
        except Exception as e:
            return JsonResponse({
                'success': False, 
                'error': f'Failed to create admin: {str(e)}'
            }, status=400)


class LogoutView(LoginRequiredMixin, View):
    def post(self, request):
        user_role = getattr(request.user, 'role', None)
        logout(request)
        return JsonResponse({
            'success': True,
            'message': 'Logged out successfully',
            'data': {'previous_role': user_role}
        })


class CurrentUserView(LoginRequiredMixin, View):
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
                    'is_active': user.is_active,
                    'date_joined': user.date_joined,
                    'last_login': user.last_login
                }
            }
        })


# ========== Quotation Status Update API ==========
class QuotationStatusUpdateView(LoginRequiredMixin, BaseAPIView):
    def put(self, request, quotation_id):
        quotation = get_object_or_404(Quotation, pk=quotation_id)
        
        # Permission check
        if request.user.role == "SALESPERSON" and quotation.assigned_to != request.user:
            return JsonResponse({
                'success': False, 
                'error': 'Permission denied'
            }, status=403)
        
        changes = []
        
        # Update status
        status = request.json.get("status")
        if status and status in dict(QuotationStatus.choices) and status != quotation.status:
            old_status = quotation.status
            quotation.status = status
            changes.append(f"Status changed from {old_status} to {status}")
        
        # Update follow-up date
        follow_up_date_str = request.json.get("follow_up_date")
        if follow_up_date_str:
            try:
                new_date = datetime.strptime(follow_up_date_str, "%Y-%m-%d").date()
                if quotation.follow_up_date != new_date:
                    old_date = quotation.follow_up_date
                    quotation.follow_up_date = new_date
                    changes.append(f"Follow-up date changed from {old_date} to {new_date}")
            except ValueError:
                return JsonResponse({
                    'success': False, 
                    'error': 'Invalid follow-up date format. Use YYYY-MM-DD.'
                }, status=400)
        
        if changes:
            quotation.save(update_fields=['status', 'follow_up_date'])
            message = "; ".join(changes)
            ActivityLog.log(
                actor=request.user,
                action=ActivityAction.QUOTATION_UPDATED,
                entity=quotation,
                message=message
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
class LeadStatusUpdateView(LoginRequiredMixin, BaseAPIView):
    def put(self, request, lead_id):
        # Only allow salesperson to update their own leads
        if request.user.role == "SALESPERSON":
            lead = get_object_or_404(Lead, pk=lead_id, assigned_to=request.user)
        else:  # Admin can update any lead
            lead = get_object_or_404(Lead, pk=lead_id)
        
        changes = []
        
        # Update status
        status = request.json.get("status")
        if status and status != lead.status:
            old_status = lead.status
            lead.status = status
            changes.append(f"Status changed from {old_status} to {status}")
        
        # Update follow-up date
        follow_up_date_str = request.json.get("follow_up_date")
        if follow_up_date_str:
            try:
                new_date = datetime.strptime(follow_up_date_str, "%Y-%m-%d").date()
                if lead.follow_up_date != new_date:
                    old_date = lead.follow_up_date
                    lead.follow_up_date = new_date
                    changes.append(f"Follow-up date changed from {old_date} to {new_date}")
            except ValueError:
                return JsonResponse({
                    'success': False, 
                    'error': 'Invalid follow-up date format. Use YYYY-MM-DD.'
                }, status=400)
        elif follow_up_date_str == "":  # Explicitly remove follow-up date
            if lead.follow_up_date:
                old_date = lead.follow_up_date
                lead.follow_up_date = None
                changes.append(f"Follow-up date removed (was {old_date})")
        
        if changes:
            lead.save(update_fields=['status', 'follow_up_date'])
            message = "; ".join(changes)
            ActivityLog.log(
                actor=request.user,
                action=ActivityAction.LEAD_UPDATED,
                entity=lead,
                message=message
            )
            
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
        else:
            return JsonResponse({
                'success': True,
                'message': 'No changes made',
                'data': {
                    'id': lead.id,
                    'status': lead.status,
                    'follow_up_date': lead.follow_up_date.isoformat() if lead.follow_up_date else None
                }
            })