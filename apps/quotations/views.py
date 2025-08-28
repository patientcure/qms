from django.db.models import Q
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import View
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from decimal import Decimal
from rest_framework import generics
import json
from apps.accounts.models import User, Roles
from .models import (
    Quotation, Lead, Customer, Product,
    TermsAndConditions, CompanyProfile, ActivityLog
)
from .forms import (
    SalespersonForm, LeadForm,
    QuotationForm,
    CustomerForm, ProductForm
)
from .choices import ActivityAction

from django.http import JsonResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .save_quotation import save_quotation_pdf


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

class LeadListView(BaseAPIView):
    def get(self, request):
        leads = Lead.objects.select_related('customer', 'assigned_to')
        data = []
        for lead in leads:
            data.append({
                'id': lead.id,
                'status': lead.status,
                'source':lead.source,
                'follow_up_date': lead.follow_up_date,
                'notes': lead.notes,
                'customer': {
                    'id': lead.customer.id if lead.customer else None,
                    'name': lead.customer.name if lead.customer else None,
                    'company_name': lead.customer.company_name if lead.customer else None
                },
                'assigned_to': {
                    'id': lead.assigned_to.id if lead.assigned_to else None,
                },
                'created_at': lead.created_at,
                'updated_at': lead.updated_at
            })
        return JsonResponse({'data': data})


class LeadCreateView( BaseAPIView):
    def post(self, request):
        form_data = {**request.POST.dict(), **request.json}
        form = LeadForm(form_data)
        
        if form.is_valid():
            lead = form.save(commit=False)
            lead.created_by = request.user
            lead.save()
            return JsonResponse({
                'success': True,
                'message': "Lead created successfully",
                'data': {
                    'id': lead.id,
                    'status': lead.status,
                }
            }, status=201)
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class LeadDetailView(AdminRequiredMixin, BaseAPIView):
    def get(self, request, lead_id):
        lead = get_object_or_404(Lead, pk=lead_id)
        return JsonResponse({
            'data': {
                'id': lead.id,
                'status': lead.status,
                'source':lead.source,
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
                    'title': lead.title,
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

class QuotationListView(BaseAPIView):
    def get(self, request):
        # if request.user.role == Roles.ADMIN:
        quotations = Quotation.objects.select_related('customer', 'assigned_to')
        # else:
        #     quotations = Quotation.objects.filter(assigned_to=request.user).select_related('customer', 'assigned_to')
        
        data = []
        for quotation in quotations:
            data.append({
                'id': quotation.id,
                'quotation_number': quotation.quotation_number,
                'status': quotation.status,
                'url': quotation.file_url,
                'subtotal': float(quotation.subtotal),
                'tax_total': float(quotation.tax_total),
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
                        'cost_price': item.cost_price,
                        'description': item.description,
                        'tax_rate': float(item.tax_rate),
                        'name' : item.name if item.name else None
                    } for item in quotation.product.all()
                ],
                'created_at': quotation.created_at,
                'emailed_at': quotation.emailed_at,
                'follow_up_date': quotation.follow_up_date
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


class QuotationDetailView(JWTAuthMixin, BaseAPIView):  # FIXED: Changed from LoginRequiredMixin
    def get(self, request, quotation_id):
        quotation = get_object_or_404(Quotation, pk=quotation_id)
        
        # Check permission
        if request.user.role == Roles.SALESPERSON and quotation.assigned_to != request.user:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        items = []
        for item in quotation.items.select_related('product'):
            items.append({
                'id': item.id,
                'quantity': float(item.quantity),
                'unit_price': float(item.unit_price),
                'tax_rate': float(item.tax_rate),
                'description': item.description,
                'product': {
                    'id': item.product.id if item.product else None,
                    'name': item.product.name if item.product else None
                }
            })
        
        return JsonResponse({
            'data': {
                'id': quotation.id,
                'quotation_number': quotation.quotation_number,
                'status': quotation.status,
                'subtotal': float(quotation.subtotal),
                'tax_total': float(quotation.tax_total),
                'total': float(quotation.total),
                'customer': {
                    'id': quotation.customer.id,
                    'name': quotation.customer.name
                },
                'assigned_to': {
                    'id': quotation.assigned_to.id if quotation.assigned_to else None,
                    'name': quotation.assigned_to.get_full_name() if quotation.assigned_to else None
                },
                'terms': {
                    'id': quotation.terms.id if quotation.terms else None
                },
                'created_at': quotation.created_at,
                'emailed_at': quotation.emailed_at,
                'follow_up_date': quotation.follow_up_date,
                'items': items
            }
        })

    def delete(self, request, quotation_id):
        quotation = get_object_or_404(Quotation, pk=quotation_id)
        
        # Check permission
        if request.user.role == Roles.SALESPERSON and quotation.assigned_to != request.user:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        quotation.delete()
        return JsonResponse({
            'success': True,
            'message': "Quotation deleted successfully"
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


# ========== Customer & Product Management ==========
class CustomerListView(AdminRequiredMixin, BaseAPIView):
    def get(self, request):
        customers = Customer.objects.all()
        data = []
        for customer in customers:
            data.append({
                'id': customer.id,
                'name': customer.name,
                'email': customer.email,
                'company_name': customer.company_name,
                'phone': customer.phone,
                'address': customer.address,
                'created_at': customer.created_at
            })
        return JsonResponse({'data': data})


class CustomerCreateView(AdminRequiredMixin, BaseAPIView):

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
                    'address': customer.address,
                    'company_name': customer.company_name,
                    'gst_number': customer.gst_number,
                    'title': customer.title,
                    'website': customer.website,
                    'primary_address': customer.primary_address,
                    'billing_address': customer.billing_address,
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
                'address': customer.address,
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
                'category': product.category,
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
                'address': customer.address
            })
        return JsonResponse({'data': data})
    
class ProductListView(BaseAPIView):
    def get(self, request):
        products = Product.objects.all()
        data = []
        for product in products:
            data.append({
                'id': product.id,
                'name': product.name,
                'category': product.category,
                'cost_price': float(product.cost_price),
                'selling_price': float(product.selling_price),
                'tax_rate': float(product.tax_rate),
                'profit_margin': float(product.profit_margin),
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
        return request.POST.dict()

    def post(self, request):
        data = self._parse_request_data(request)
        if data is None:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        form = ProductForm(data)
        if form.is_valid():
            product = form.save()
            return JsonResponse({
                'success': True,
                'message': 'Product created successfully',
                'data': {
                    'id': product.id,
                    'name': product.name,
                    'category': product.category,
                    'cost_price': float(product.cost_price),
                    'selling_price': float(product.selling_price),
                    'tax_rate': float(product.tax_rate),
                    'profit_margin': float(product.profit_margin),
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

        form = ProductForm(data, instance=product)
        if form.is_valid():
            product = form.save(commit=False)

            update_fields = [
                f for f in data.keys()
                if f in form.cleaned_data and hasattr(product, f)
            ]
            for field in update_fields:
                setattr(product, field, form.cleaned_data[field])

            product.save(update_fields=update_fields)

            updated_data = {field: getattr(product, field) for field in update_fields}
            updated_data['id'] = product.id

            return JsonResponse({
                'success': True,
                'message': 'Product updated successfully',
                'data': updated_data
            })

        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    def delete(self, request):
        product_id = request.GET.get('id')
        if not product_id:
            return JsonResponse({'error': 'Product ID required in query params'}, status=400)

        product = get_object_or_404(Product, pk=product_id)
        product.active = False
        product.save(update_fields=['active'])
        return JsonResponse({
            'success': True,
            'message': 'Product deactivated successfully',
            'data': {'active': product.active}
        })

class ProductDetailView(JWTAuthMixin, BaseAPIView):
    def get(self, request, product_id):
        product = get_object_or_404(Product, pk=product_id)
        return JsonResponse({
            'data': {
                'id': product.id,
                'name': product.name,
                'category': product.category,
                'cost_price': float(product.cost_price),
                'selling_price': float(product.selling_price),
                'tax_rate': float(product.tax_rate),
                'profit_margin': float(product.profit_margin),
                'unit': product.unit,
                'description': product.description,
                'weight': float(product.weight) if product.weight else None,
                'dimensions': product.dimensions,
                'warranty_months': product.warranty_months,
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
                    'category': product.category,
                    'cost_price': float(product.cost_price),
                    'selling_price': float(product.selling_price),
                    'tax_rate': float(product.tax_rate),
                    'profit_margin': float(product.profit_margin),
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
