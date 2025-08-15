from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView
from .forms import QuotationForm, QuotationItemFormSet, CustomerForm, ProductForm
from .models import Quotation, Customer, Product, TermsAndConditions, EmailTemplate,CompanyProfile
from .choices import QuotationStatus, ActivityAction
from .models import ActivityLog
from .utils import generate_next_quotation_number
from .services.pdf import render_quotation_pdf
from .services.google_drive import upload_pdf_to_drive
from .services.email import send_quotation_email
from .models import EmailLog
# Step-1 pipeline wrapper (already written)
from . import utils as _u
from . import services
from .models import Lead
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.template.loader import render_to_string
from decimal import Decimal
from django.views.generic.edit import CreateView
from django.forms.models import model_to_dict
from .forms import CustomerForm, ProductForm

class CustomerCreateAjaxView(CreateView):
    model = Customer
    form_class = CustomerForm

    def form_valid(self, form):
        customer = form.save()
        return JsonResponse({'success': True, 'customer': model_to_dict(customer)})

    def form_invalid(self, form):
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

class ProductCreateAjaxView(CreateView):
    model = Product
    form_class = ProductForm

    def form_valid(self, form):
        product = form.save()
        return JsonResponse({'success': True, 'product': model_to_dict(product)})

    def form_invalid(self, form):
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class QuotationLivePreviewView(View):
    def post(self, request, *args, **kwargs):
        try:
            # Parse incoming POST data (simulate quotation object)
            customer_id = request.POST.get('customer')
            customer = Customer.objects.filter(id=customer_id).first()

            # Simulate items from formset data
            items = []
            subtotal = Decimal('0.00')
            tax_total = Decimal('0.00')
            for i in range(0, int(request.POST.get('form-TOTAL_FORMS', 0))):
                product_id = request.POST.get(f'form-{i}-product')
                qty = Decimal(request.POST.get(f'form-{i}-quantity', '0'))
                price = Decimal(request.POST.get(f'form-{i}-unit_price', '0'))
                tax_rate = Decimal(request.POST.get(f'form-{i}-tax_rate', '0'))
                if product_id and qty > 0:
                    subtotal += qty * price
                    tax_total += qty * price * (tax_rate / Decimal('100.00'))
                    product = Product.objects.filter(id=product_id).first()
                    items.append({
                        'product': product,
                        'quantity': qty,
                        'unit_price': price,
                        'tax_rate': tax_rate,
                        'description': request.POST.get(f'form-{i}-description', ''),
                    })

            total = subtotal + tax_total

            # Context for rendering
            context = {
                'quotation': {
                    'quotation_number': 'PREVIEW',
                    'customer': customer,
                    'subtotal': subtotal,
                    'tax_total': tax_total,
                    'total': total,
                },
                'company': CompanyProfile.objects.first(),
                'items': items,
            }

            html = render_to_string('pdf/quotation.html', context)
            return JsonResponse({'html': html})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

# ---------- Create ----------
class QuotationCreateView(LoginRequiredMixin, View):
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
            quotation.save()  # triggers number + totals on save
            formset.instance = quotation
            formset.save()
            # ensure totals up-to-date and auto-assign if needed
            quotation.recalculate_totals()
            quotation.auto_assign_if_needed()
            ActivityLog.log(actor=request.user, action=ActivityAction.QUOTATION_CREATED, entity=quotation, message="Created via UI")
            return redirect(reverse("quotations.create") + f"?q={quotation.pk}")
        return render(request, self.template_name, {"form": form, "formset": formset})

# ---------- Live HTML preview ----------
class QuotationPreviewView(LoginRequiredMixin, View):
    """Returns the same HTML used by the PDF renderer for right-pane preview."""
    def get(self, request, pk):
        q = get_object_or_404(Quotation.objects.select_related("customer", "terms"), pk=pk)
        items = q.items.select_related("product").all()
        company = None
        from .models import CompanyProfile
        company = CompanyProfile.objects.first()
        return render(request, "pdf/quotation.html", {"quotation": q, "items": items, "company": company})

# ---------- Submit & Send (PDF -> SendGrid -> Drive -> status/logs) ----------
class QuotationSendView(LoginRequiredMixin, View):
    def post(self, request, pk):
        quotation = get_object_or_404(Quotation, pk=pk)
        try:
            # reuse the Step-1 pipeline
            from . import services as _svc
            _u.send_and_archive_quotation(quotation)  # updates status + logs inside
            return JsonResponse({"ok": True, "status": quotation.status, "emailed_at": timezone.localtime(quotation.emailed_at).strftime("%Y-%m-%d %H:%M") if quotation.emailed_at else ""})
        except Exception as e:
            return JsonResponse({"ok": False, "error": str(e)}, status=400)

# ---------- List + Filters + CSV ----------
class QuotationListView(LoginRequiredMixin, ListView):
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
        # Provide choices list directly for template iteration
        context['status_choices'] = list(Quotation._meta.get_field('status').choices)
        return context


class QuotationCSVExportView(LoginRequiredMixin, View):
    def get(self, request):
        # export current filtered result
        view = QuotationListView()
        view.request = request
        queryset = view.get_queryset()
        from . import models as m
        # reuse Step-1 CSV exporter
        from .models import export_quotations_csv  # inside the same file in Step-1 snippet
        return export_quotations_csv(queryset)

# ---------- Dashboard ----------
class SalesDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "quotations/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["upcoming"] = Quotation.objects.filter(
            follow_up_date__isnull=False,
            status__in=[QuotationStatus.PENDING, QuotationStatus.IN_PROGRESS, QuotationStatus.MAIL_SENT]
        ).order_by("follow_up_date")[:50]
        return ctx

# ---------- Modal: Add-new (AJAX) ----------
class CustomerCreateAjaxView(LoginRequiredMixin, View):
    def post(self, request):
        form = CustomerForm(request.POST)
        if form.is_valid():
            obj = form.save()
            return JsonResponse({"id": obj.id, "name": str(obj)})
        return JsonResponse({"errors": form.errors}, status=400)

class ProductCreateAjaxView(LoginRequiredMixin, View):
    def post(self, request):
        form = ProductForm(request.POST)
        if form.is_valid():
            obj = form.save()
            return JsonResponse({"id": obj.id, "name": str(obj)})
        return JsonResponse({"errors": form.errors}, status=400)
    
@method_decorator(csrf_exempt, name='dispatch')
class QuotationLivePreviewView(View):
    def post(self, request, *args, **kwargs):
        try:
            # Parse form data and build preview context
            context = self._build_preview_context(request.POST)
            html = render_to_string('pdf/quotation.html', context)
            return JsonResponse({'html': html})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    def _build_preview_context(self, post_data):
        # Helper method to construct the preview context
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
