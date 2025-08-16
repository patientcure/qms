from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, ListView, CreateView, UpdateView
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.db.models import Count, Q
from django.contrib import messages
from django.views import View
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.forms.models import model_to_dict
from decimal import Decimal
from apps.accounts.models import User, Roles
from .models import (
    Quotation, Lead, Customer, Product,
    TermsAndConditions, EmailTemplate,
    CompanyProfile, ActivityLog, EmailLog
)
from .forms import (
    SalespersonForm, LeadForm,
    QuotationForm, QuotationItemFormSet,
    CustomerForm, ProductForm
)
from .choices import LeadStatus, QuotationStatus, ActivityAction
from .utils import generate_next_quotation_number, send_and_archive_quotation


class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = "accounts/admin_dashboard.html"
    model = Quotation
    paginate_by = 25
    context_object_name = 'quotations'

    def test_func(self):
        return self.request.user.role == Roles.ADMIN

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'customer', 'assigned_to', 'terms'
        ).prefetch_related('items')

        status = self.request.GET.get('status')
        customer = self.request.GET.get('customer')
        assigned_to = self.request.GET.get('assigned_to')
        date_from = self.request.GET.get('from')
        date_to = self.request.GET.get('to')

        if status:
            queryset = queryset.filter(status=status)
        if customer:
            queryset = queryset.filter(customer_id=customer)
        if assigned_to:
            queryset = queryset.filter(assigned_to_id=assigned_to)
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Salespeople data
        context['salespeople'] = User.objects.filter(role=Roles.SALESPERSON).annotate(
            quotation_count=Count('quotations', distinct=True),
            lead_count=Count('leads', distinct=True)
        )

        # Quotations data
        context['status_choices'] = QuotationStatus.choices
        context['all_customers'] = Customer.objects.all()
        context['salespeople_list'] = User.objects.filter(role=Roles.SALESPERSON)

        # Leads data
        leads_queryset = Lead.objects.select_related('customer', 'assigned_to')
        
        # Apply filters to leads if they exist
        lead_status = self.request.GET.get('lead_status')
        lead_assigned_to = self.request.GET.get('lead_assigned_to')
        lead_date_from = self.request.GET.get('lead_from')
        lead_date_to = self.request.GET.get('lead_to')
        
        if lead_status:
            leads_queryset = leads_queryset.filter(status=lead_status)
        if lead_assigned_to:
            leads_queryset = leads_queryset.filter(assigned_to_id=lead_assigned_to)
        if lead_date_from:
            leads_queryset = leads_queryset.filter(created_at__date__gte=lead_date_from)
        if lead_date_to:
            leads_queryset = leads_queryset.filter(created_at__date__lte=lead_date_to)
            
        context['leads'] = leads_queryset
        context['lead_status_choices'] = LeadStatus.choices

        return context


class SalespersonMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin for salesperson-related views"""
    def test_func(self):
        return self.request.user.role == Roles.ADMIN


class CreateSalespersonView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = User
    form_class = SalespersonForm
    template_name = "accounts/salesperson_form.html"
    
    def test_func(self):
        return self.request.user.role == Roles.ADMIN
    
    def form_valid(self, form):
        user = form.save(commit=False)
        user.role = Roles.SALESPERSON
        
        if form.cleaned_data.get('password1'):
            user.set_password(form.cleaned_data['password1'])
        
        user.save()
        messages.success(self.request, f"Salesperson {user.get_full_name()} created successfully")
        return redirect('quotations:admin_dashboard')

class EditSalespersonView(SalespersonMixin, UpdateView):
    """Edit an existing salesperson account"""
    model = User
    form_class = SalespersonForm
    template_name = "accounts/salesperson_form.html"
    pk_url_kwarg = 'user_id'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['password_required'] = False
        return kwargs
    
    def form_valid(self, form):
        user = form.save()
        messages.success(self.request, f"Salesperson {user.get_full_name()} updated successfully")
        return redirect('quotations:admin_dashboard')


class ToggleSalespersonStatusView(SalespersonMixin, View):
    """Activate/deactivate a salesperson account"""
    def post(self, request, user_id):
        user = get_object_or_404(User, pk=user_id, role=Roles.SALESPERSON)
        user.is_active = not user.is_active
        user.save()
        
        action = "activated" if user.is_active else "deactivated"
        messages.success(request, f"Salesperson {user.get_full_name()} {action} successfully")
        return redirect('quotations:admin_dashboard')


class LeadMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin for lead-related views"""
    def test_func(self):
        return self.request.user.role == Roles.ADMIN


class CreateLeadView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Lead
    form_class = LeadForm
    template_name = "accounts/lead_form.html"
    
    def test_func(self):
        return self.request.user.role == Roles.ADMIN
    
    def form_valid(self, form):
        lead = form.save(commit=False)
        lead.created_by = self.request.user
        lead.save()
        messages.success(self.request, "Lead created successfully")
        return redirect('quotations:admin_dashboard')


class EditLeadView(LeadMixin, UpdateView):
    """Edit an existing lead"""
    model = Lead
    form_class = LeadForm
    template_name = "accounts/lead_form.html"
    pk_url_kwarg = 'lead_id'
    
    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Lead updated successfully")
        return redirect('quotations:admin_dashboard')


class AssignLeadView(LeadMixin, View):
    """Assign a lead to a salesperson"""
    def post(self, request, lead_id):
        lead = get_object_or_404(Lead, pk=lead_id)
        assigned_to_id = request.POST.get('assigned_to')
        
        if assigned_to_id:
            salesperson = get_object_or_404(User, pk=assigned_to_id, role=Roles.SALESPERSON)
            lead.assigned_to = salesperson
            lead.save()
            messages.success(request, f"Lead assigned to {salesperson.get_full_name()}")
        else:
            lead.assigned_to = None
            lead.save()
            messages.success(request, "Lead assignment removed")
            
        return redirect('quotations:admin_dashboard')


# ========== Quotation Views ==========
class QuotationMixin(LoginRequiredMixin):
    """Mixin for quotation-related views"""
    pass


class AdminQuotationCreateView(QuotationMixin, UserPassesTestMixin, View):
    """Admin view for creating quotations"""
    template_name = "quotations/create.html"
    
    def test_func(self):
        return self.request.user.role == Roles.ADMIN
    
    def get(self, request):
        form = QuotationForm()
        formset = QuotationItemFormSet()
        return render(request, self.template_name, {
            "form": form, 
            "formset": formset,
            "salespeople": User.objects.filter(role=Roles.SALESPERSON)
        })

    @transaction.atomic
    def post(self, request):
        form = QuotationForm(request.POST)
        formset = QuotationItemFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            quotation = form.save(commit=False)
            
            if not quotation.assigned_to:
                quotation.auto_assign_if_needed()
                
            quotation.save()
            formset.instance = quotation
            formset.save()
            quotation.recalculate_totals()
            
            messages.success(request, f"Quotation {quotation.quotation_number} created successfully")
            return redirect('quotations:admin_dashboard')
            
        return render(request, self.template_name, {
            "form": form, 
            "formset": formset,
            "salespeople": User.objects.filter(role=Roles.SALESPERSON)
        })


class QuotationCreateView(QuotationMixin, View):
    """Create a new quotation"""
    template_name = "quotations/create.html"

    def get(self, request):
        form = QuotationForm()
        formset = QuotationItemFormSet()
        return render(request, self.template_name, {"form": form, "formset": formset})

    @transaction.atomic
    def post(self, request):
        form = QuotationForm(request.POST)
        formset = QuotationItemFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            quotation = form.save(commit=False)
            quotation.save()
            formset.instance = quotation
            formset.save()
            quotation.recalculate_totals()
            quotation.auto_assign_if_needed()
            ActivityLog.log(
                actor=request.user, 
                action=ActivityAction.QUOTATION_CREATED, 
                entity=quotation, 
                message="Created via UI"
            )
            return redirect(reverse("quotations.create") + f"?q={quotation.pk}")
        return render(request, self.template_name, {"form": form, "formset": formset})


class QuotationPreviewView(QuotationMixin, View):
    """Preview quotation HTML"""
    def get(self, request, pk):
        q = get_object_or_404(
            Quotation.objects.select_related("customer", "terms"), 
            pk=pk
        )
        items = q.items.select_related("product").all()
        company = CompanyProfile.objects.first()
        return render(
            request, 
            "pdf/quotation.html", 
            {"quotation": q, "items": items, "company": company}
        )


class QuotationSendView(QuotationMixin, View):
    """Send quotation to customer"""
    def post(self, request, pk):
        quotation = get_object_or_404(Quotation, pk=pk)
        try:
            send_and_archive_quotation(quotation)
            return JsonResponse({
                "ok": True,
                "status": quotation.status,
                "emailed_at": timezone.localtime(quotation.emailed_at).strftime("%Y-%m-%d %H:%M") 
                if quotation.emailed_at else ""
            })
        except Exception as e:
            return JsonResponse({"ok": False, "error": str(e)}, status=400)


class QuotationListView(QuotationMixin, ListView):
    """List all quotations with filters"""
    template_name = "quotations/list.html"
    model = Quotation
    paginate_by = 20
    context_object_name = 'quotations'

    def get_queryset(self):
        qs = super().get_queryset().select_related("customer", "assigned_to")
        q = self.request.GET.get("q", "")
        status = self.request.GET.get("status", "")
        product = self.request.GET.get("product", "")
        date_from = self.request.GET.get("from", "")
        date_to = self.request.GET.get("to", "")

        if q:
            qs = qs.filter(
                Q(quotation_number__icontains=q) |
                Q(customer__name__icontains=q) |
                Q(customer__email__icontains=q)
            )
        if status:
            qs = qs.filter(status=status)
        if product:
            qs = qs.filter(items__product_id=product)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        return qs.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = list(Quotation._meta.get_field('status').choices)
        return context


class QuotationCSVExportView(QuotationMixin, View):
    """Export quotations to CSV"""
    def get(self, request):
        view = QuotationListView()
        view.request = request
        queryset = view.get_queryset()
        from .models import export_quotations_csv
        return export_quotations_csv(queryset)


# ========== Salesperson Dashboard ==========
class SalespersonDashboardView(QuotationMixin, TemplateView):
    """Dashboard for salespersons"""
    template_name = "accounts/salesperson_dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        ctx['quotations'] = Quotation.objects.filter(
            assigned_to=user
        ).order_by('-created_at')
        
        ctx['leads'] = Lead.objects.filter(
            assigned_to=user
        ).order_by('-created_at')

        ctx['upcoming_followups'] = ctx['quotations'].filter(
            follow_up_date__isnull=False,
            status__in=[
                QuotationStatus.PENDING,
                QuotationStatus.IN_PROGRESS,
                QuotationStatus.MAIL_SENT
            ]
        ).order_by("follow_up_date")[:20]

        # Pass status choices explicitly
        ctx['status_choices'] = QuotationStatus.choices  # <-- add this

        return ctx


# ========== AJAX Views ==========
class CustomerCreateAjaxView(QuotationMixin, View):
    """AJAX endpoint for creating customers"""
    def post(self, request):
        form = CustomerForm(request.POST)
        if form.is_valid():
            obj = form.save()
            return JsonResponse({"id": obj.id, "name": str(obj)})
        return JsonResponse({"errors": form.errors}, status=400)


class ProductCreateAjaxView(QuotationMixin, View):
    """AJAX endpoint for creating products"""
    def post(self, request):
        form = ProductForm(request.POST)
        if form.is_valid():
            obj = form.save()
            return JsonResponse({"id": obj.id, "name": str(obj)})
        return JsonResponse({"errors": form.errors}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class QuotationLivePreviewView(View):
    """Live preview of quotation"""
    def post(self, request, *args, **kwargs):
        try:
            context = self._build_preview_context(request.POST)
            html = render_to_string('pdf/quotation.html', context)
            return JsonResponse({'html': html})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    def _build_preview_context(self, post_data):
        customer = Customer.objects.filter(id=post_data.get('customer')).first()
        items = []
        subtotal = Decimal('0.00')
        tax_total = Decimal('0.00')

        for i in range(0, int(post_data.get('form-TOTAL_FORMS', 0))):
            product_id = post_data.get(f'form-{i}-product')
            qty = Decimal(post_data.get(f'form-{i}-quantity', '0'))
            price = Decimal(post_data.get(f'form-{i}-unit_price', '0'))
            tax_rate = Decimal(post_data.get(f'form-{i}-tax_rate', '0'))

            if product_id and qty > 0:
                product = Product.objects.filter(id=product_id).first()
                items.append({
                    'product': product,
                    'quantity': qty,
                    'unit_price': price,
                    'tax_rate': tax_rate,
                    'description': post_data.get(f'form-{i}-description', ''),
                })
                subtotal += qty * price
                tax_total += qty * price * (tax_rate / Decimal('100.00'))

        return {
            'quotation': {
                'quotation_number': 'PREVIEW',
                'customer': customer,
                'subtotal': subtotal,
                'tax_total': tax_total,
                'total': subtotal + tax_total,
            },
            'company': CompanyProfile.objects.first(),
            'items': items,
        }


class GetProductDetailsView(QuotationMixin, View):
    """AJAX endpoint for product details"""
    def get(self, request, product_id):
        product = Product.objects.filter(pk=product_id).first()
        if product:
            return JsonResponse({
                'unit_price': str(product.unit_price),
                'tax_rate': str(product.tax_rate)
            })
        return JsonResponse({'error': 'Product not found'}, status=404)

class QuotationEditView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Quotation
    form_class = QuotationForm
    template_name = "quotations/edit.html"
    pk_url_kwarg = "pk"

    def test_func(self):
        return self.request.user.role == Roles.ADMIN

    def form_valid(self, form):
        quotation = form.save()
        messages.success(self.request, f"Quotation {quotation.quotation_number} updated successfully")
        return redirect("quotations:admin_dashboard")
