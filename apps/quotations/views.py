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
from django.db.models import ProtectedError
import json
from apps.accounts.models import User, Roles
from .models import (
    Quotation, Lead, Customer, Product,ProductImage,
    TermsAndConditions, CompanyProfile, ActivityLog,Category
)
from .forms import (
    SalespersonForm, LeadForm,
    QuotationForm,
    CustomerForm, ProductForm
)
from .choices import ActivityAction,QuotationStatus,LeadStatus
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
from datetime import datetime
from django.db.models import Count, Q, Case, When, F, FloatField
from django.db.models.deletion import ProtectedError

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
        lead_filter = request.GET.get('filter', 'active')

        # Base queryset with related objects
        leads = Lead.objects.select_related(
            "customer", "assigned_to", "created_by"
        )
        if lead_filter != 'converted':
            leads = leads.filter(status=LeadStatus.CONVERTED)
        else:
            # 'active' means all leads that are NOT converted
            leads = leads.exclude(status=LeadStatus.CONVERTED)
        # If lead_filter is something else (e.g., 'all'), we just get all leads
        
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
            "activity_logs": logs_by_lead.get(lead.id, []),  # Latest 10 activities
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
                status=QuotationStatus.DRAFT
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
                message="Created via API",
                customer = quotation.customer,
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
            salesperson = get_object_or_404(User, pk=assigned_to_id, role__in=[Roles.SALESPERSON, Roles.ADMIN])
            lead.assigned_to = salesperson
            message = f"Lead assigned to {salesperson.get_full_name()}"

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

class QuotationListView(JWTAuthMixin, BaseAPIView):
    def get(self, request):
        user = request.user
        try:
            quotations = Quotation.objects.select_related(
                'customer', 'assigned_to', 'created_by'
            ).prefetch_related(
                'terms', 'details__product'
            )

            quotations = quotations.exclude(Q(file_url__isnull=True) | Q(file_url=''))            
            if getattr(user, "role", None) == Roles.SALESPERSON:
                quotations = quotations.filter(Q(assigned_to=user) | Q(created_by=user))
            else:
                logger.info(f"User '{user.username}' is not a salesperson (or is admin). Showing all quotations.")

            quotation_ids = quotations.values_list("id", flat=True)
            
            activity_logs = ActivityLog.objects.filter(
                entity_type="Quotation",
                entity_id__in=[str(qid) for qid in quotation_ids]
            ).select_related("actor").order_by("-created_at")
            logs_by_quotation = {}
            for log in activity_logs:
                quotation_id = int(log.entity_id)
                if quotation_id not in logs_by_quotation:
                    logs_by_quotation[quotation_id] = []
                logs_by_quotation[quotation_id].append({
                    "id": log.id,
                    "action": log.action,
                    "message": log.message,
                    "actor": {
                        "id": log.actor.id if log.actor else None,
                        "name": log.actor.get_full_name() if log.actor else "System"
                    },
                    "created_at": log.created_at
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
                    'created_by': {
                        'id': quotation.created_by.id if quotation.created_by else None,
                        'name': quotation.created_by.get_full_name() if quotation.created_by else None
                    },
                    'created_at': quotation.created_at,
                    'emailed_at': quotation.emailed_at,
                    'follow_up_date': quotation.follow_up_date,
                    'activity_logs': logs_by_quotation.get(quotation.id, [])[:10],
                })
            return JsonResponse({'data': data})
        
        except Exception as e:
            return JsonResponse({'error': 'An internal server error occurred.'}, status=500)
       
class QuotationPDFView(BaseAPIView):
    def get(self, request, quotation_id):
        quotation = get_object_or_404(Quotation, pk=quotation_id)
        
        try:
            pdf_url = save_quotation_pdf(quotation, request)
            
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

        quotation_number = quotation.quotation_number

        if quotation.lead_id:
            Lead.objects.filter(pk=quotation.lead_id).delete()

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
            salesperson = get_object_or_404(User, pk=assigned_to_id, role__in=[Roles.SALESPERSON, Roles.ADMIN])
            quotation.assigned_to = salesperson
            message = f"Quotation assigned to {salesperson.get_full_name()}"
        # else:
        #     quotation.assigned_to = None
        #     message = "Quotation assignment removed"
            
        quotation.save()
        
        log_action = ActivityAction.LEAD_ASSIGNED if assigned_to_id else ActivityAction.LEAD_UPDATED
        
        ActivityLog.log(
            actor=request.user,
            action=log_action,
            entity=quotation,
            message=message,
            customer = quotation.customer,
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
                if lead.status == LeadStatus.CONVERTED:
                    continue
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
    
class AllCustomerListView(JWTAuthMixin,BaseAPIView):
    def get(self, request):
        user = getattr(request, "user", None)
        
        if user and getattr(user, "role", None) == Roles.SALESPERSON:
            leads_qs = Lead.objects.filter(Q(assigned_to=user) | Q(created_by=user))

            quotations_qs = Quotation.objects.filter(Q(assigned_to=user) | Q(created_by=user))
            customer_filter = Q(leads__in=leads_qs) | Q(quotations__in=quotations_qs)

            customers = Customer.objects.filter(
                customer_filter
            ).prefetch_related(
                Prefetch('leads', queryset=leads_qs, to_attr='filtered_leads'),
                Prefetch('quotations', queryset=quotations_qs, to_attr='filtered_quotations'),
                'filtered_leads__assigned_to',
                'filtered_quotations__assigned_to',
                'filtered_quotations__details__product',
                'filtered_quotations__terms'
            ).distinct().order_by('-created_at')
        else:
            customers = Customer.objects.prefetch_related(
                'leads__assigned_to', 
                'quotations__assigned_to',
                'quotations__details__product',
                'quotations__terms'
            ).order_by('-created_at')

        all_lead_ids = set()
        all_quotation_ids = set()
        for customer in customers:
            leads = getattr(customer, 'filtered_leads', customer.leads.all())
            quotations = getattr(customer, 'filtered_quotations', customer.quotations.all())
            for lead in leads:
                all_lead_ids.add(lead.id)
                if lead.quotation_id:
                    all_quotation_ids.add(lead.quotation_id)
            for quotation in quotations:
                all_quotation_ids.add(quotation.id)

        quotations_map = {
            q.id: q.file_url 
            for q in Quotation.objects.filter(id__in=all_quotation_ids).only('id', 'file_url')
        }

        lead_activity_logs = ActivityLog.objects.filter(
            entity_type='Lead',
            entity_id__in=[str(lid) for lid in all_lead_ids]
        ).select_related('actor').order_by('-created_at')

        logs_by_lead = {}
        for log in lead_activity_logs:
            lead_id = int(log.entity_id)
            if lead_id not in logs_by_lead:
                logs_by_lead[lead_id] = []
            logs_by_lead[lead_id].append({
                'id': log.id, 'action': log.action, 'message': log.message,
                'actor': {'id': log.actor.id if log.actor else None, 'name': log.actor.get_full_name() if log.actor else 'System'},
                'created_at': log.created_at
            })

        quotation_activity_logs = ActivityLog.objects.filter(
            entity_type='Quotation',
            entity_id__in=[str(qid) for qid in all_quotation_ids]
        ).select_related('actor').order_by('-created_at')

        logs_by_quotation = {}
        for log in quotation_activity_logs:
            quotation_id = int(log.entity_id)
            if quotation_id not in logs_by_quotation:
                logs_by_quotation[quotation_id] = []
            logs_by_quotation[quotation_id].append({
                'id': log.id, 'action': log.action, 'message': log.message,
                'actor': {'id': log.actor.id if log.actor else None, 'name': log.actor.get_full_name() if log.actor else 'System'},
                'created_at': log.created_at
            })

        data = []
        for customer in customers:
            leads = getattr(customer, 'filtered_leads', customer.leads.all())
            quotations = getattr(customer, 'filtered_quotations', customer.quotations.all())
            leads_data = []
            for lead in leads:
                leads_data.append({
                    'id': lead.id,
                    'status': lead.status,
                    'lead_source': lead.lead_source,
                    'file_url': quotations_map.get(lead.quotation_id),
                    'quotation_id': lead.quotation_id,
                    'assigned_to': {
                        'id': lead.assigned_to.id if lead.assigned_to else None,
                        'name': lead.assigned_to.get_full_name() if lead.assigned_to else None,
                    },
                    'created_at': lead.created_at,
                    'activity_logs': logs_by_lead.get(lead.id, [])[:10]
                })
            quotations_data = []
            for quotation in quotations:
                if not quotation.file_url:
                    continue
                quotations_data.append({
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
                        {'id': term.id, 'title': term.title}
                        for term in quotation.terms.all()
                    ],   
                    'items':[
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
                    'activity_logs': logs_by_quotation.get(quotation.id, [])[:10]
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
                'quotations': quotations_data,
            })
        return JsonResponse({'data': data})
    
class CustomerCreateView(JWTAuthMixin,BaseAPIView):

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
            return JsonResponse({'error': 'Customer ID is required.'}, status=400)

        try:
            customer = Customer.objects.get(pk=customer_id)
            customer_id_to_confirm = customer.id
            customer.delete()
            return JsonResponse({
                'success': True,
                'message': f'Customer with ID {customer_id_to_confirm} has been permanently deleted.',
            })
        except Customer.DoesNotExist:
            return JsonResponse({'error': f'Customer with ID {customer_id} not found.'}, status=404)
        except ProtectedError:
            return JsonResponse({
                'error': f'Customer with ID {customer_id} cannot be deleted because they are associated with existing leads or quotations.'
            }, status=409)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': f'An unexpected error occurred: {str(e)}'}, status=500)

class CustomerDetailView(AdminRequiredMixin, BaseAPIView):
    def get(self, request, customer_id):
        customer = get_object_or_404(Customer, pk=customer_id)

        logs = customer.activity_logs.select_related("actor").all()

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
                'logs': [
                    {
                        'id': log.id,
                        'action': log.action,
                        'actor': {
                            'id': log.actor.id if log.actor else None,
                            'name': log.actor.get_full_name() if log.actor else "System",
                            'email': log.actor.email if log.actor else None,
                        },
                        'entity_type': log.entity_type,
                        'entity_id': log.entity_id,
                        'message': log.message,
                        'created_at': log.created_at,
                    }
                    for log in logs
                ]
            }
        })

class FilteredCustomerListView(JWTAuthMixin, BaseAPIView):
    def get(self, request):
        user = getattr(request, 'user', None)
        try:
            if user and getattr(user, 'role', None) == Roles.SALESPERSON:
                logger.debug(
                    "FilteredCustomerListView: building queryset for salesperson",
                    extra={"user_id": user.id, "username": getattr(user, "username", None)}
                )
                customers_qs = Customer.objects.filter(
                    Q(leads__assigned_to=user)
                    | Q(leads__created_by=user)
                    | Q(quotations__assigned_to=user)
                    | Q(quotations__created_by=user)
                    | Q(created_by=user)
                ).distinct()
            else:
                logger.debug(
                    "FilteredCustomerListView: fetching all customers (non-salesperson or admin)",
                    extra={"user_id": getattr(user, "id", None)}
                )
                customers_qs = Customer.objects.all()

            customers = customers_qs.order_by('-created_at')
            data = []
            for c in customers:
                data.append({
                    'id': c.id,
                    'name': c.name,
                    'company_name': c.company_name,
                    'primary_address': c.primary_address,
                    'email': c.email,
                    'phone': c.phone,
                    'created_at': c.created_at.isoformat() if c.created_at else None,
                })

            logger.info(
                "FilteredCustomerListView: returning customers",
                extra={"user_id": getattr(user, "id", None), "count": len(data)}
            )
            return JsonResponse({'data': data}, safe=False)

        except Exception as e:
            logger.exception(
                "FilteredCustomerListView: unexpected error while fetching customers for user_id=%s",
                getattr(user, "id", None)
            )
            return JsonResponse({'error': 'An internal server error occurred.'}, status=500)

class UnfilteredCustomerListView(JWTAuthMixin, BaseAPIView):
    """Returns all customers without any role-based filtering. Requires authentication."""
    
    def get(self, request):
        try:
            customers = Customer.objects.all().order_by('-created_at')
            
            data = []
            for customer in customers:
                data.append({
                    'id': customer.id,
                    'name': customer.name,
                    'email': customer.email,
                    'phone': customer.phone,
                    'company_name': customer.company_name,
                    'gst_number': customer.gst_number,
                    'website': customer.website,
                    'shipping_address': customer.shipping_address,
                    'billing_address': customer.billing_address,
                    'primary_address': customer.primary_address,
                    'title': customer.title,
                    'created_at': customer.created_at.isoformat() if customer.created_at else None,
                })

            return JsonResponse({'success': True, 'data': data}, safe=False)
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
        
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
        products = Product.objects.all().prefetch_related('images')        
        data = []
        for product in products:
            image_url = []
            if product.image:
                image_url.append(request.build_absolute_uri(product.image.url))
            data.append({
                'id': product.id,
                'name': product.name,
                'category': product.category.name if product.category else None,
                'cost_price': float(product.cost_price),
                'selling_price': float(product.selling_price),
                'unit': product.unit,                
                'images': image_url,               
                'description': product.description,
                'is_available': product.is_available,
                'active': product.active,
                'brand': product.brand,
                'dimensions' : product.dimensions,
                'weight': float(product.weight) if product.weight else None,
                'warranty_months': product.warranty_months,
                'created_at': product.created_at
            })
        return JsonResponse({'data': data})


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

class UserStatsView(JWTAuthMixin, BaseAPIView):
    def get(self, request, user_id=None):
        # If user_id is not provided, use the authenticated user
        if user_id:
            user = get_object_or_404(User, pk=user_id)
        else:
            user = request.user

        quotations = Quotation.objects.filter(created_by=user)
        leads = Lead.objects.filter(created_by=user)
        assigned_quotations = Quotation.objects.filter(assigned_to=user)
        assigned_leads = Lead.objects.filter(assigned_to=user)
        sent_quotations = quotations.filter(status=QuotationStatus.SENT)
        closed_leads = leads.filter(status='QUALIFIED')
        open_leads = leads.exclude(status='QUALIFIED')

        stats = {
            'user_id': user.id,
            'name': user.get_full_name(),
            'role': user.role,
            'total_quotations_created': quotations.count(),
            'total_leads_created': leads.count(),
            'total_quotations_assigned': assigned_quotations.count(),
            'total_leads_assigned': assigned_leads.count(),
            'sent_quotations': sent_quotations.count(),
            'open_leads': open_leads.count(),
            'closed_leads': closed_leads.count(),
            'last_login': user.last_login,
            'date_joined': user.date_joined,
        }
        return JsonResponse({'data': stats})
    
class TopPerfomerView(BaseAPIView):
    def get(self, request):
        """
        Calculates and returns a ranked list of top-performing salespeople
        based on quotation count and conversion rate within a given timeframe.
        """
        try:
            # --- 1. Handle Query Parameters using request.GET ---
            start_date_str = request.GET.get('start_date')
            end_date_str = request.GET.get('end_date')
            limit = request.GET.get('limit', 10)

            logger.info(
                f"TopPerformerView request received with params: start_date='{start_date_str}', "
                f"end_date='{end_date_str}', limit='{limit}'"
            )

            try:
                limit = int(limit)
            except (ValueError, TypeError):
                logger.warning(f"Invalid limit parameter '{limit}'. Falling back to default of 10.")
                limit = 10

            # --- 2. Build Date Filter for Quotations ---
            quotation_filters = Q()
            if start_date_str:
                quotation_filters &= Q(quotations__created_at__gte=datetime.strptime(start_date_str, '%Y-%m-%d').date())
            if end_date_str:
                quotation_filters &= Q(quotations__created_at__lte=datetime.strptime(end_date_str, '%Y-%m-%d').date())
            logger.info("Querying for salespeople and annotating performance stats...")
            sent_filter = ~Q(status=QuotationStatus.DRAFT)
            accepted_filter = Q(status=QuotationStatus.ACCEPTED)

            salespeople = User.objects.filter(role=Roles.SALESPERSON).annotate(
                total_sent=Count(
                    'quotations',
                    filter=Q(quotations__in=Quotation.objects.filter(sent_filter, **{k.replace('quotations__',''):v for k,v in quotation_filters.children}))
                ),
                total_accepted=Count(
                    'quotations',
                    filter=Q(quotations__in=Quotation.objects.filter(accepted_filter, **{k.replace('quotations__',''):v for k,v in quotation_filters.children}))
                )
            ).annotate(
                conversion_rate=Case(
                    When(total_sent=0, then=0.0),
                    default=(F('total_accepted') * 100.0 / F('total_sent')),
                    output_field=FloatField()
                )
            )

            # --- 4. Rank Performers ---
            top_performers = salespeople.filter(total_sent__gt=0).order_by('-conversion_rate', '-total_sent')
            
            logger.debug(f"Top Performers Query SQL: {top_performers.query}")

            top_performers = top_performers[:limit]

            result = [
                {
                    'user_id': user.id,
                    'name': user.get_full_name() or user.username,
                    'total_sent': user.total_sent,
                    'total_accepted': user.total_accepted,
                    'conversion_rate': round(user.conversion_rate, 2),
                    'email':user.email,
                    'phone':user.phone_number,
                }
                for user in top_performers
            ]
            logger.info(f"Successfully found {len(result)} top performers.")

            return JsonResponse({'data': result})

        except ValueError as e:
            logger.warning(f"Date format error in TopPerformerView: {e}")
            return JsonResponse({'error': f"Invalid date format: {e}. Use YYYY-MM-DD."}, status=400)
        
        except Exception as e:
            logger.error(
                "An unexpected error occurred in TopPerformerView",
                exc_info=True
            )
            return JsonResponse({'error': 'An internal server error occurred.'}, status=500)