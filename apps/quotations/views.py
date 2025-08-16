from decimal import Decimal
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.generic import ListView, TemplateView
from django.forms.models import model_to_dict
from django.template.loader import render_to_string

from .forms import (
    QuotationForm,
    QuotationItemFormSet,
    CustomerForm,
    ProductForm
)
from .models import (
    Quotation,
    Customer,
    Product,
    TermsAndConditions,
    EmailTemplate,
    CompanyProfile,
    ActivityLog,
    EmailLog,
    Lead
)
from .choices import QuotationStatus, ActivityAction
from .utils import generate_next_quotation_number, send_and_archive_quotation


# ---------- Create Quotation ----------
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
            # update totals and auto-assign
            quotation.recalculate_totals()
            quotation.auto_assign_if_needed()
            ActivityLog.log(actor=request.user, action=ActivityAction.QUOTATION_CREATED, entity=quotation, message="Created via UI")
            return redirect(reverse("quotations.create") + f"?q={quotation.pk}")
        return render(request, self.template_name, {"form": form, "formset": formset})


# ---------- Quotation HTML Preview ----------
class QuotationPreviewView(LoginRequiredMixin, View):
    """Returns the same HTML used by the PDF renderer for right-pane preview."""
    def get(self, request, pk):
        q = get_object_or_404(Quotation.objects.select_related("customer", "terms"), pk=pk)
        items = q.items.select_related("product").all()
        company = CompanyProfile.objects.first()
        return render(request, "pdf/quotation.html", {"quotation": q, "items": items, "company": company})


# ---------- Submit & Send ----------
class QuotationSendView(LoginRequiredMixin, View):
    def post(self, request, pk):
        quotation = get_object_or_404(Quotation, pk=pk)
        try:
            send_and_archive_quotation(quotation)
            return JsonResponse({
                "ok": True,
                "status": quotation.status,
                "emailed_at": timezone.localtime(quotation.emailed_at).strftime("%Y-%m-%d %H:%M") if quotation.emailed_at else ""
            })
        except Exception as e:
            return JsonResponse({"ok": False, "error": str(e)}, status=400)


# ---------- Quotation List + Filters ----------
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
        context['status_choices'] = list(Quotation._meta.get_field('status').choices)
        return context


# ---------- CSV Export ----------
class QuotationCSVExportView(LoginRequiredMixin, View):
    def get(self, request):
        view = QuotationListView()
        view.request = request
        queryset = view.get_queryset()
        from .models import export_quotations_csv
        return export_quotations_csv(queryset)


# ---------- Sales Dashboard ----------
class SalesDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "quotations/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["upcoming"] = Quotation.objects.filter(
            follow_up_date__isnull=False,
            status__in=[
                QuotationStatus.PENDING,
                QuotationStatus.IN_PROGRESS,
                QuotationStatus.MAIL_SENT
            ]
        ).order_by("follow_up_date")[:50]
        return ctx


# ---------- AJAX: Create Customer ----------
class CustomerCreateAjaxView(LoginRequiredMixin, View):
    def post(self, request):
        form = CustomerForm(request.POST)
        if form.is_valid():
            obj = form.save()
            return JsonResponse({"id": obj.id, "name": str(obj)})
        return JsonResponse({"errors": form.errors}, status=400)


# ---------- AJAX: Create Product ----------
class ProductCreateAjaxView(LoginRequiredMixin, View):
    def post(self, request):
        form = ProductForm(request.POST)
        if form.is_valid():
            obj = form.save()
            return JsonResponse({"id": obj.id, "name": str(obj)})
        return JsonResponse({"errors": form.errors}, status=400)


# ---------- Live Quotation Preview (Form Data) ----------
@method_decorator(csrf_exempt, name='dispatch')
class QuotationLivePreviewView(View):
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
