from django.db.models import Q
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import View
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .utils_quotation import get_quotation_response_data
from decimal import Decimal
from rest_framework import generics
import json
from apps.accounts.models import User, Roles
from .models import (
    Quotation, Lead, Customer, Product,
    TermsAndConditions, CompanyProfile, ActivityLog,Category
)
from .forms import (
    SalespersonForm, LeadForm,
    QuotationForm,
    CustomerForm, ProductForm
)
from .choices import ActivityAction,QuotationStatus
from .serializers import CategorySerializer
from rest_framework import viewsets
from django.http import JsonResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .save_quotation import save_quotation_pdf
from django.db.models import Prefetch
import logging
from django.http import JsonResponse
from django.db import transaction
from django.conf import settings
logger = logging.getLogger(__name__)


class JWTAuthMixin:
    """Base mixin to authenticate requests using JWT access token."""

    def dispatch(self, request, *args, **kwargs):
        authenticator = JWTAuthentication()
        result = authenticator.authenticate(request)

        if result is None:
            from rest_framework.exceptions import AuthenticationFailed
            raise AuthenticationFailed("Authentication credentials were not provided or invalid.")

        user, _ = result
        request.user = user 

        return super().dispatch(request, *args, **kwargs)


class AdminRequiredMixin(JWTAuthMixin):
    def dispatch(self, request, *args, **kwargs):
        # First run JWT authentication
        response = super().dispatch(request, *args, **kwargs)
        if isinstance(response, JsonResponse):  # means authentication failed
            return response

        if not (request.user and getattr(request.user, "role", None) == "ADMIN"):
            return JsonResponse({"error": "Admin access required"}, status=403)
        return super(JWTAuthMixin, self).dispatch(request, *args, **kwargs)


class SalespersonRequiredMixin(JWTAuthMixin):
    def dispatch(self, request, *args, **kwargs):
        # First run JWT authentication
        response = super().dispatch(request, *args, **kwargs)
        if isinstance(response, JsonResponse):  # means authentication failed
            return response

        if not (request.user and getattr(request.user, "role", None) == "SALESPERSON"):
            return JsonResponse({"error": "Salesperson access required"}, status=403)
        return super(JWTAuthMixin, self).dispatch(request, *args, **kwargs)


@method_decorator(csrf_exempt, name='dispatch')
class BaseAPIView(View):
    """Base class for all API views with JSON parsing"""
    
    def dispatch(self, request, *args, **kwargs):
        if request.content_type == 'application/json' and request.body:
            try:
                request.json = json.loads(request.body)
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Invalid JSON'}, status=400)
        else:
            request.json = {}
        return super().dispatch(request, *args, **kwargs)


# ========== Salesperson Management ==========
class SalespersonListView(AdminRequiredMixin, BaseAPIView):
    def get(self, request):
        salespeople = User.objects.filter(role=Roles.SALESPERSON)
        data = []
        for person in salespeople:
            data.append({
                'id': person.id,
                'first_name': person.first_name,
                'last_name': person.last_name,
                'email': person.email,
                'is_active': person.is_active,
                'quotation_count': person.quotations.count(),
                'lead_count': person.leads.count(),
                'created_at': person.date_joined,
                'last_login': person.last_login
            })
        return JsonResponse({'data': data})


class SalespersonCreateView(AdminRequiredMixin, BaseAPIView):
    def post(self, request):
        form_data = {**request.POST.dict(), **request.json}
        form = SalespersonForm(form_data)
        
        if form.is_valid():
            user = form.save(commit=False)
            user.role = Roles.SALESPERSON
            
            if form.cleaned_data.get('password1'):
                user.set_password(form.cleaned_data['password1'])
            
            user.save()
            return JsonResponse({
                'success': True,
                'message': f"Salesperson {user.get_full_name()} created successfully",
                'data': {
                    'id': user.id,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email,
                    'is_active': user.is_active
                }
            }, status=201)
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class SalespersonDetailView(AdminRequiredMixin, BaseAPIView):
    def get(self, request, user_id):
        salesperson = get_object_or_404(User, pk=user_id, role=Roles.SALESPERSON)
        return JsonResponse({
            'data': {
                'id': salesperson.id,
                'first_name': salesperson.first_name,
                'last_name': salesperson.last_name,
                'email': salesperson.email,
                'is_active': salesperson.is_active,
                'quotation_count': salesperson.quotations.count(),
                'lead_count': salesperson.leads.count(),
                'created_at': salesperson.date_joined,
                'last_login': salesperson.last_login
            }
        })

    def put(self, request, user_id):
        salesperson = get_object_or_404(User, pk=user_id, role=Roles.SALESPERSON)
        form_data = {**request.POST.dict(), **request.json}
        form = SalespersonForm(form_data, instance=salesperson)
        
        if form.is_valid():
            user = form.save()
            return JsonResponse({
                'success': True,
                'message': f"Salesperson {user.get_full_name()} updated successfully",
                'data': {
                    'id': user.id,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email,
                    'is_active': user.is_active
                }
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    def delete(self, request, user_id):
        salesperson = get_object_or_404(User, pk=user_id, role=Roles.SALESPERSON)
        salesperson.is_active = not salesperson.is_active
        salesperson.save()  
        
        action = "activated" if salesperson.is_active else "deactivated"
        return JsonResponse({
            'success': True,
            'message': f"Salesperson {salesperson.get_full_name()} {action} successfully",
            'data': {'is_active': salesperson.is_active}
        })
#region Leads
class LeadListView(JWTAuthMixin, BaseAPIView):
    def get(self, request):
        user = request.user

        # Base queryset with related objects
        leads = Lead.objects.select_related(
            "customer", "assigned_to", "created_by"
        )

        # Restrict SALESPERSON to only their own leads
        if getattr(user, "role", None) == Roles.SALESPERSON:
            leads = leads.filter(Q(assigned_to=user) | Q(created_by=user))

        # Prefetch quotations (bulk fetch only needed fields)
        quotation_ids = leads.exclude(quotation_id__isnull=True).values_list(
            "quotation_id", flat=True
        )
        quotations = Quotation.objects.filter(id__in=quotation_ids).only("id", "file_url")
        quotation_map = {q.id: q.file_url for q in quotations}

        # Fetch activity logs for all leads in bulk
        lead_ids = leads.values_list("id", flat=True)
        activity_logs = ActivityLog.objects.filter(
            entity_type="Lead",
            entity_id__in=[str(lid) for lid in lead_ids]
        ).select_related("actor").order_by("-created_at")

        # Group logs by entity_id
        logs_by_lead = {}
        for log in activity_logs:
            lead_id = int(log.entity_id)
            if lead_id not in logs_by_lead:
                logs_by_lead[lead_id] = []
            logs_by_lead[lead_id].append({
                "id": log.id,
                "action": log.action,
                "message": log.message,
                "actor": {
                    "id": log.actor.id if log.actor else None,
                    "name": log.actor.get_full_name() if log.actor else "System"
                },
                "created_at": log.created_at
            })

        # Serialize leads
        data = [self.serialize_lead(lead, quotation_map, logs_by_lead) for lead in leads]

        return JsonResponse({"data": data}, status=200, safe=False)

    @staticmethod
    def serialize_lead(lead, quotation_map, logs_by_lead):
        customer = lead.customer
        assigned_to = lead.assigned_to

        return {
            "id": lead.id,
            "status": lead.status,
            "source": lead.lead_source,
            "follow_up_date": lead.follow_up_date,
            "notes": lead.notes or "",
            "priority": lead.priority,
            "customer": {
                "id": customer.id if customer else None,
                "name": getattr(customer, "name", None),
                "company_name": getattr(customer, "company_name", None),
                "phone": getattr(customer, "phone", None),
                "email": getattr(customer, "email", None),
                "primary_address": getattr(customer, "primary_address", None),
            },
            "assigned_to": {
                "id": assigned_to.id if assigned_to else None,
                "name": assigned_to.get_full_name() if assigned_to else None,
            },
            "quotation": lead.quotation_id,
            "file_url": quotation_map.get(lead.quotation_id),
            "created_at": lead.created_at,
            "updated_at": lead.updated_at,
            "created_by": lead.created_by.get_full_name() if lead.created_by else None,
            "activity_logs": logs_by_lead.get(lead.id, [])[:10],  # Latest 10 activities
        }



class LeadCreateView(JWTAuthMixin, BaseAPIView):
    @transaction.atomic
    def post(self, request):
        try:
            # 1. Pass all request data directly to the form.
            form = LeadForm(request.json)

            # 2. Return immediately if the form is invalid
            if not form.is_valid():
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)

            # 3. Create lead instance but do not save yet
            lead = form.save(commit=False)

            # 4. Set created_by if user is SALESPERSON
            if getattr(request.user, 'role', None) == 'SALESPERSON':
                lead.created_by = request.user

            # 5. Auto-assign lead if not assigned
            if not lead.assigned_to:
                salesperson = Lead.get_least_loaded_salesperson()
                if salesperson:
                    lead.assigned_to = salesperson

            # 6. Create a corresponding empty quotation
            quotation = Quotation.objects.create(
                customer=lead.customer,
                assigned_to=lead.assigned_to,
                status=QuotationStatus.PENDING
            )
            lead.quotation_id = quotation.id

            # 7. Save lead and update quotation with lead_id
            lead.save()
            quotation.lead_id = lead.id
            quotation.save(update_fields=['lead_id'])

            # 8. Log the activity
            ActivityLog.log(
                actor=request.user,
                action=ActivityAction.LEAD_CREATED,
                entity=lead,
                message="Created via API"
            )

            # 9. Prepare response data
            response_data = {
                'id': lead.id,
                'status': lead.status,
                'priority': lead.priority,
                'customer': {
                    'id': lead.customer.id,
                    'name': lead.customer.name,
                    'phone': lead.customer.phone,
                },
                'assigned_to': {
                    'id': lead.assigned_to.id,
                    'name': lead.assigned_to.get_full_name()
                } if lead.assigned_to else None,
                'quotation': {
                    'id': quotation.id,
                    'quotation_number': quotation.quotation_number,
                    'lead_id': quotation.lead_id
                }
            }

            return JsonResponse({
                'success': True,
                'message': "Lead and corresponding quotation created successfully",
                'data': response_data
            }, status=201)

        except Exception as e:
            import traceback
            return JsonResponse({
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }, status=500)

class LeadDetailView(AdminRequiredMixin, BaseAPIView):
    def get(self, request, lead_id):
        lead = get_object_or_404(Lead, pk=lead_id)
        ActivityLog.log(
            actor=request.user,
            action=ActivityAction.LEAD_UPDATED,
            entity=lead,
            message=lead.status
        )
        return JsonResponse({
            'data': {
                'id': lead.id,
                'status': lead.status,
                'source':lead.lead_source,
                'follow_up_date': lead.follow_up_date,
                'notes': lead.notes,
                'customer': {
                    'id': lead.customer.id if lead.customer else None,
                    'name': lead.customer.name if lead.customer else None
                },
                'assigned_to': {
                    'id': lead.assigned_to.id if lead.assigned_to else None,
                },
                'created_at': lead.created_at,
                'updated_at': lead.updated_at
            }
        })

    def put(self, request, lead_id):
        lead = get_object_or_404(Lead, pk=lead_id)
        form_data = {**request.POST.dict(), **request.json}
        form = LeadForm(form_data, instance=lead)
        
        if form.is_valid():
            lead = form.save()
            return JsonResponse({
                'success': True,
                'message': "Lead updated successfully",
                'data': {
                    'id': lead.id,
                    'status': lead.status,
                    'priority': lead.priority
                }
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    def delete(self, request, lead_id):
        lead = get_object_or_404(Lead, pk=lead_id)
        lead.delete()
        return JsonResponse({
            'success': True,
            'message': "Lead deleted successfully"
        })


class LeadAssignView(AdminRequiredMixin, BaseAPIView):
    def post(self, request, lead_id):
        lead = get_object_or_404(Lead, pk=lead_id)
        assigned_to_id = request.json.get('assigned_to_id') or request.POST.get('assigned_to_id')
        
        if assigned_to_id:
            salesperson = get_object_or_404(User, pk=assigned_to_id, role=Roles.SALESPERSON)
            lead.assigned_to = salesperson
            message = f"Lead assigned to {salesperson.get_full_name()}"
        else:
            lead.assigned_to = None
            message = "Lead assignment removed"
            
        lead.save()
        return JsonResponse({
            'success': True, 
            'message': message,
            'data': {
                'assigned_to': {
                    'id': lead.assigned_to.id if lead.assigned_to else None,
                    'name': lead.assigned_to.get_full_name() if lead.assigned_to else None
                }
            }
        })
#region Quotations
class QuotationListView(JWTAuthMixin,BaseAPIView):
    def get(self, request):
        user = request.user
        quotations = Quotation.objects.select_related(
            'customer', 'assigned_to'
        ).prefetch_related(
            'terms', 'details__product'
        )

        if user.role == 'SALESPERSON':
            quotations = quotations.filter(Q(assigned_to=user) | Q(created_by=user))

        # Get activity logs for all quotations
        quotation_ids = quotations.values_list('id', flat=True)
        activity_logs = ActivityLog.objects.filter(
            entity_type='Quotation',
            entity_id__in=[str(qid) for qid in quotation_ids]
        ).select_related('actor').order_by('-created_at')
        
        # Group logs by entity_id
        logs_by_quotation = {}
        for log in activity_logs:
            quotation_id = int(log.entity_id)
            if quotation_id not in logs_by_quotation:
                logs_by_quotation[quotation_id] = []
            logs_by_quotation[quotation_id].append({
                'id': log.id,
                'action': log.action,
                'message': log.message,
                'actor': {
                    'id': log.actor.id if log.actor else None,
                    'name': log.actor.get_full_name() if log.actor else 'System'
                },
                'created_at': log.created_at
            })

        data = []
        for quotation in quotations:
            data.append({
                'id': quotation.id,
                'quotation_number': quotation.quotation_number,
                'status': quotation.status,
                'url': quotation.file_url,
                'discount': float(quotation.discount) if quotation.discount else 0.0,
                'discount_type': quotation.discount_type,
                'subtotal': float(quotation.subtotal),
                'tax_rate': float(quotation.tax_rate), 
                'total': float(quotation.total),
                'terms': [
                    {
                        'id': term.id,
                        'title': term.title,
                    }
                    for term in quotation.terms.all()
                ],   
                'customer': {
                    'id': quotation.customer.id,
                    'name': quotation.customer.name,
                    'email': quotation.customer.email,
                    'phone': quotation.customer.phone,
                    'company_name': quotation.customer.company_name,
                    'address': quotation.customer.primary_address
                },
                'products':[
                    {
                        'id': item.id,
                        'product_id': item.product.id,
                        'name' : item.product.name,
                        'selling_price': float(item.selling_price),
                        'quantity': item.quantity,
                        'percentage_discount': float(item.discount) if item.discount else 0.0,
                        'description': item.product.description if hasattr(item.product, 'description') else '',
                    } for item in quotation.details.all() 
                ],
                'assigned_to': {
                    'id': quotation.assigned_to.id if quotation.assigned_to else None,
                    'name': quotation.assigned_to.get_full_name() if quotation.assigned_to else None
                },
                'created_at': quotation.created_at,
                'emailed_at': quotation.emailed_at,
                'follow_up_date': quotation.follow_up_date,
                'activity_logs': logs_by_quotation.get(quotation.id, [])[:10]  # Latest 10 activities
            })
        return JsonResponse({'data': data})
        
class QuotationPDFView(BaseAPIView):
    def get(self, request, quotation_id):
        quotation = get_object_or_404(Quotation, pk=quotation_id)
        
        # Check permission
        # if request.user.role == Roles.SALESPERSON and quotation.assigned_to != request.user:
        #     return JsonResponse({'error': 'Permission denied'}, status=403)
        
        try:
            pdf_path, pdf_url = save_quotation_pdf(quotation, request)
            
            return JsonResponse({
                'success': True,
                'data': {
                    'pdf_url': pdf_url,
                    'quotation_number': quotation.quotation_number
                }
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f"Failed to generate PDF: {str(e)}"
            }, status=500)


class QuotationDetailView(BaseAPIView):
    def get(self, request, quotation_id):
        """
        Fetches the complete details of a single quotation, including items and terms.
        """
        try:
            quotation = get_object_or_404(
                Quotation.objects.prefetch_related('details__product', 'terms'), 
                pk=quotation_id
            )
            
            lead = Lead.objects.filter(quotation_id=quotation.id).first()
            
            response_data = get_quotation_response_data(quotation, lead)
            
            return JsonResponse({
                'success': True,
                'data': response_data
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    def delete(self, request, quotation_id):

        quotation = get_object_or_404(Quotation, pk=quotation_id)
        
        if hasattr(request.user, 'role') and request.user.role == Roles.SALESPERSON and quotation.assigned_to != request.user:
            return JsonResponse({'success': False, 'error': 'You do not have permission to delete this quotation.'}, status=403)
        
        quotation_number = quotation.quotation_number
        quotation.delete()
        
        return JsonResponse({
            'success': True,
            'message': f"Quotation {quotation_number} deleted successfully."
        })



class QuotationSendView(JWTAuthMixin, BaseAPIView):
    def post(self, request, quotation_id):
        quotation = get_object_or_404(Quotation, pk=quotation_id)
        
        if request.user.role == Roles.SALESPERSON and quotation.assigned_to != request.user:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        try:
            print(f"Sending quotation {quotation.quotation_number} to {quotation.customer.email}")
            return JsonResponse({
                'success': True,
                'message': 'Quotation sent successfully',
                'data': {
                    'status': quotation.status,
                    'emailed_at': timezone.localtime(quotation.emailed_at).isoformat() if quotation.emailed_at else None
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class QuotationAssignView(AdminRequiredMixin, BaseAPIView):
    def post(self, request, quotation_id):
        quotation = get_object_or_404(Quotation, pk=quotation_id)
        assigned_to_id = request.json.get('assigned_to_id') or request.POST.get('assigned_to_id')
        
        if assigned_to_id:
            salesperson = get_object_or_404(User, pk=assigned_to_id, role=Roles.SALESPERSON)
            quotation.assigned_to = salesperson
            message = f"Quotation assigned to {salesperson.get_full_name()}"
        else:
            quotation.assigned_to = None
            message = "Quotation assignment removed"
            
        quotation.save()
        
        ActivityLog.log(
            actor=request.user,
            action=ActivityAction.QUOTATION_ASSIGNED if assigned_to_id else ActivityAction.QUOTATION_UNASSIGNED,
            entity=quotation,
            message=message
        )
        
        return JsonResponse({
            'success': True, 
            'message': message,
            'data': {
                'assigned_to': {
                    'id': quotation.assigned_to.id if quotation.assigned_to else None,
                    'name': quotation.assigned_to.get_full_name() if quotation.assigned_to else None
                }
            }
        })

#region Customer
# ========== Customer & Product Management ==========
class CustomerListView(JWTAuthMixin,BaseAPIView):
    def get(self, request):
        user = request.user

        leads_qs = Lead.objects.select_related('assigned_to', 'created_by')

        if getattr(user, 'role', None) == 'SALESPERSON':
            leads_qs = leads_qs.filter(Q(assigned_to=user) | Q(created_by=user))

        customers = Customer.objects.prefetch_related(
            Prefetch('leads', queryset=leads_qs, to_attr='filtered_leads')
        )

        data = []
        for customer in customers:
            filtered_leads = getattr(customer, 'filtered_leads', [])
            if not filtered_leads:
                continue

            leads_data = []
            for lead in filtered_leads:
                file_url = None
                if lead.quotation_id:
                    try:
                        file_url = Quotation.objects.get(pk=lead.quotation_id).file_url
                    except Quotation.DoesNotExist:
                        pass

                leads_data.append({
                    'id': lead.id,
                    'status': lead.status,
                    'lead_source': lead.lead_source,
                    'file_url': file_url,
                    'quotation': lead.quotation_id,
                    'assigned_to': {
                        'id': lead.assigned_to.id if lead.assigned_to else None,
                        'name': lead.assigned_to.get_full_name() if lead.assigned_to else None,
                    },
                    'created_at': lead.created_at,
                    'created_by': lead.created_by.get_full_name() if lead.created_by else None,
                })

            data.append({
                'id': customer.id,
                'name': customer.name,
                'email': customer.email,
                'company_name': customer.company_name,
                'gst_number': customer.gst_number,
                'website': customer.website,
                'shipping_address': customer.shipping_address,
                'billing_address': customer.billing_address,
                'primary_address': customer.primary_address,
                'title': customer.title,
                'phone': customer.phone,
                'created_at': customer.created_at,
                'leads': leads_data,
            })

        return JsonResponse({'data': data}, safe=False)
    
class AllCustomerListView( BaseAPIView):
    def get(self, request):
        customers = Customer.objects.prefetch_related(
            Prefetch('leads')
        )
        data = []
        for customer in customers:
            leads = []
            for lead in customer.leads.all():
                file_url = None
                if lead.quotation_id:
                    try:
                        file_url = Quotation.objects.get(pk=lead.quotation_id).file_url
                    except Quotation.DoesNotExist:
                        file_url = None

                leads.append({
                    'id': lead.id,
                    'status': lead.status,
                    'lead_source': lead.lead_source,
                    'file_url': file_url,
                    'quotation': lead.quotation_id,
                    'assigned_to': {
                        'id': lead.assigned_to.id if lead.assigned_to else None,
                        'name': lead.assigned_to.get_full_name() if lead.assigned_to else None,
                    },
                    'created_at': lead.created_at,
                })

            data.append({
                'id': customer.id,
                'name': customer.name,
                'email': customer.email,
                'company_name': customer.company_name,
                'gst_number': customer.gst_number,
                'website': customer.website,
                'shipping_address': customer.shipping_address,
                'billing_address': customer.billing_address,
                'primary_address': customer.primary_address,
                'title': customer.title,
                'phone': customer.phone,
                'created_at': customer.created_at,
                'leads': leads,
            })

        return JsonResponse({'data': data}, safe=False)

class CustomerCreateView( BaseAPIView):

    def _parse_request_data(self, request):
        if request.content_type == 'application/json':
            try:
                return json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError:
                return None
        return request.POST.dict()

    def post(self, request):
        data = self._parse_request_data(request)
        if data is None:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        form = CustomerForm(data)
        if form.is_valid():
            customer = form.save()
            return JsonResponse({
                'success': True,
                'message': 'Customer created successfully',
                'data': {
                    'id': customer.id,
                    'name': customer.name,
                    'email': customer.email,
                    'phone': customer.phone,
                    'company_name': customer.company_name,
                    'gst_number': customer.gst_number,
                    'title': customer.title,
                    'website': customer.website,
                    'primary_address': customer.primary_address,
                    'billing_address': customer.billing_address,
                    'shipping_address': customer.shipping_address,
                }
            }, status=201)

        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    def put(self, request):
        customer_id = request.GET.get('id')
        if not customer_id:
            return JsonResponse({'error': 'Customer ID required in query params'}, status=400)

        customer = get_object_or_404(Customer, pk=customer_id)

        data = self._parse_request_data(request)
        if data is None:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        form = CustomerForm(data, instance=customer)
        if form.is_valid():
            customer = form.save(commit=False)
            update_fields = [
                f for f in data.keys()
                if f in form.cleaned_data and hasattr(customer, f)
            ]
            for field in update_fields:
                setattr(customer, field, form.cleaned_data[field])

            customer.save(update_fields=update_fields)

            updated_data = {field: getattr(customer, field) for field in update_fields}
            updated_data['id'] = customer.id

            return JsonResponse({
                'success': True,
                'message': 'Customer updated successfully',
                'data': updated_data
            })

        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    def delete(self, request):
        customer_id = request.GET.get('id')
        if not customer_id:
            return JsonResponse({'error': 'Customer ID required in query params'}, status=400)

        customer = get_object_or_404(Customer, pk=customer_id)
        customer.delete()
        return JsonResponse({
            'success': True,
            'message': 'Customer deleted successfully'
        })

class CustomerDetailView(AdminRequiredMixin, BaseAPIView):
    def get(self, request, customer_id):
        customer = get_object_or_404(Customer, pk=customer_id)
        return JsonResponse({
            'data': {
                'id': customer.id,
                'name': customer.name,
                'email': customer.email,
                'phone': customer.phone,
                'company_name': customer.company_name,
                'created_at': customer.created_at,
                'gst_number': customer.gst_number,
                'title': customer.title,
                'website': customer.website,
                'primary_address': customer.primary_address,
                'billing_address': customer.billing_address,
            }
        })

    def put(self, request, customer_id):
        customer = get_object_or_404(Customer, pk=customer_id)
        form_data = {**request.POST.dict(), **request.json}
        form = CustomerForm(form_data, instance=customer)
        
        if form.is_valid():
            customer = form.save()
            return JsonResponse({
                'success': True,
                'message': 'Customer updated successfully',
                'data': {
                    'id': customer.id,
                    'name': customer.name,
                    'email': customer.email,
                    'phone': customer.phone
                }
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    def delete(self, request, customer_id):
        customer = get_object_or_404(Customer, pk=customer_id)
        customer.delete()
        return JsonResponse({
            'success': True,
            'message': 'Customer deleted successfully'
        })

class ProductSearchView(JWTAuthMixin, BaseAPIView):
    def get(self, request):
        name = request.GET.get('name', '').strip()
        if not name:
            return JsonResponse({'error': 'Missing "name" parameter'}, status=400)
        products = Product.objects.filter(Q(name__icontains=name))
        data = []
        for product in products:
            data.append({
                'id': product.id,
                'name': product.name,
                'category': product.category.name if product.category else None,
                'cost_price': float(product.cost_price),
                'selling_price': float(product.selling_price),
                'tax_rate': float(product.tax_rate),
                'unit': product.unit,
                'description': product.description,
                'is_available': product.is_available,
                'active': product.active,
                'brand': product.brand
            })
        return JsonResponse({'data': data})

class CustomerSearchView(BaseAPIView):
    def get(self, request):
        name = request.GET.get('name', '').strip()
        if not name:
            return JsonResponse({'error': 'Missing "name" parameter'}, status=400)
        customers = Customer.objects.filter(Q(name__icontains=name))
        data = []
        for customer in customers:
            data.append({
                'id': customer.id,
                'name': customer.name,
                'email': customer.email,
                'company_name': customer.company_name,
                'phone': customer.phone,
                'address': customer.primary_address
            })
        return JsonResponse({'data': data})
#region Product Management
class ProductListView(BaseAPIView):
    def get(self, request):
        products = Product.objects.all()
        data = []
        for product in products:
            data.append({
                'id': product.id,
                'name': product.name,
                'category': product.category.name if product.category else None,
                'cost_price': float(product.cost_price),
                'selling_price': float(product.selling_price),
                'unit': product.unit,
                'description': product.description,
                'is_available': product.is_available,
                'active': product.active,
                'brand': product.brand,
                'weight': float(product.weight) if product.weight else None,
                'warranty_months': product.warranty_months,
                'created_at': product.created_at
            })
        return JsonResponse({'data': data})


class ProductCreateView(JWTAuthentication, BaseAPIView):
    def _parse_request_data(self, request):
        if request.content_type == 'application/json':
            try:
                return json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError:
                return None
        return request.POST.copy() # Use copy to make it mutable

    def _handle_category(self, data):
        category_data = data.get('category')
        if category_data and isinstance(category_data, str):
            # Use get_or_create to find or create the category
            category, created = Category.objects.get_or_create(
                name__iexact=category_data, # Case-insensitive check
                defaults={'name': category_data}
            )
            # Replace the category name in the data with its ID for the form
            data['category'] = category.pk
        return data

    def post(self, request):
        data = self._parse_request_data(request)
        if data is None:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        data = self._handle_category(data)

        form = ProductForm(data)
        if form.is_valid():
            product = form.save()
            return JsonResponse({
                'success': True,
                'message': 'Product created successfully',
                'data': {
                    'id': product.id,
                    'name': product.name,
                    'category': product.category.name if product.category else None,
                    'cost_price': float(product.cost_price or 0),
                    'selling_price': float(product.selling_price or 0),
                    'unit': product.unit
                }
            }, status=201)

        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    def put(self, request):
        product_id = request.GET.get('id')
        if not product_id:
            return JsonResponse({'error': 'Product ID required in query params'}, status=400)

        product = get_object_or_404(Product, pk=product_id)

        data = self._parse_request_data(request)
        if data is None:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        data = self._handle_category(data)

        form = ProductForm(data, instance=product)
        if form.is_valid():
            # Only save the fields that were actually sent in the request
            update_fields = [f for f in data.keys() if f in form.cleaned_data]
            
            # If category was updated, ensure it's in the list
            if 'category' in data and 'category' not in update_fields:
                update_fields.append('category')

            product = form.save(commit=False)
            product.save(update_fields=update_fields)
            
            # Prepare response data, handling Decimal serialization
            updated_data = {}
            for field in update_fields:
                value = getattr(product, field)
                if isinstance(value, Decimal):
                    updated_data[field] = float(value)
                elif isinstance(value, Category):
                     updated_data[field] = value.name
                else:
                    updated_data[field] = value
            updated_data['id'] = product.id


            return JsonResponse({
                'success': True,
                'message': 'Product updated successfully',
                'data': updated_data
            })

        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    def delete(self, request):
        """Handles deactivating a product (soft delete)."""
        product_id = request.GET.get('id')
        if not product_id:
            return JsonResponse({'error': 'Product ID required in query params'}, status=400)

        product = get_object_or_404(Product, pk=product_id)
        product.active = False
        product.save(update_fields=['active'])
        return JsonResponse({
            'success': True,
            'message': 'Product deactivated successfully',
            'data': {'id': product.id, 'active': product.active}
        })

class ProductDetailView(JWTAuthMixin, BaseAPIView):
    def get(self, request, product_id):
        product = get_object_or_404(Product, pk=product_id)
        return JsonResponse({
            'data': {
                'id': product.id,
                'name': product.name,
                'category': product.category.name if product.category else None,
                'selling_price': float(product.selling_price),
                'unit': product.unit,
                'description': product.description,
                'weight': float(product.weight) if product.weight else None,
                'dimensions': product.dimensions,
                'brand': product.brand,
                'is_available': product.is_available,
                'active': product.active,
                'created_at': product.created_at
            }
        })

    def put(self, request, product_id):
        product = get_object_or_404(Product, pk=product_id)
        form_data = {**request.POST.dict(), **request.json}
        form = ProductForm(form_data, instance=product)
        
        if form.is_valid():
            product = form.save()
            return JsonResponse({
                'success': True,
                'message': 'Product updated successfully',
                'data': {
                    'id': product.id,
                    'name': product.name,
                    'category': product.category.name if product.category else None,
                    'selling_price': float(product.selling_price),
                    'tax_rate': float(product.tax_rate),
                    'unit': product.unit
                }
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    def delete(self, request, product_id):
        product = get_object_or_404(Product, pk=product_id)
        product.active = False
        product.save()
        return JsonResponse({
            'success': True,
            'message': 'Product deactivated successfully',
            'data': {'active': product.active}
        })

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    authentication_classes = []
    permission_classes = []

#region Dashboard Stats
class AdminDashboardStatsView(AdminRequiredMixin, BaseAPIView):
    def get(self, request):
        stats = {
            'total_salespeople': User.objects.filter(role=Roles.SALESPERSON).count(),
            'active_salespeople': User.objects.filter(role=Roles.SALESPERSON, is_active=True).count(),
            'total_quotations': Quotation.objects.count(),
            'total_leads': Lead.objects.count(),
            'total_customers': Customer.objects.count(),
            'total_products': Product.objects.filter(is_active=True).count()
        }
        return JsonResponse({'data': stats})


class SalespersonDashboardStatsView(SalespersonRequiredMixin, BaseAPIView):
    def get(self, request):
        user = request.user
        stats = {
            'my_quotations': user.quotations.count(),
            'my_leads': user.leads.count(),
            'pending_quotations': user.quotations.filter(status='DRAFT').count(),
            'sent_quotations': user.quotations.filter(status='SENT').count(),
            'open_leads': user.leads.exclude(status='CLOSED').count()
        }
        return JsonResponse({'data': stats})
