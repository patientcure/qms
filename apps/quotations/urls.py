# urls.py - Complete URL configuration

from django.urls import path
from .terms_views import (
    TermsListView,
    TermsCreateView,
)
from .quotation_create_view import(
    QuotationCreateView
)
from .views import (
    # Salesperson Management
    SalespersonListView,
    SalespersonCreateView,
    SalespersonDetailView,
    
    # Lead Management
    LeadListView,
    LeadCreateView,
    LeadDetailView,
    LeadAssignView,
    
    # Quotation Management
    QuotationListView,
    QuotationDetailView,
    QuotationSendView,
    QuotationAssignView,
    QuotationPDFView,
    
    # Customer Management
    CustomerListView,
    CustomerCreateView,
    CustomerDetailView,
    
    # Product Management
    ProductListView,
    ProductCreateView,
    ProductDetailView,
    
    # Dashboard Stats
    AdminDashboardStatsView,
    SalespersonDashboardStatsView,
)

app_name = "quotations"

urlpatterns = [
    # ========== Salesperson Management API ==========
    path('api/salespeople/', SalespersonListView.as_view(), name='salesperson_list'),
    path('api/salespeople/create/', SalespersonCreateView.as_view(), name='salesperson_create'),
    path('api/salespeople/<int:user_id>/', SalespersonDetailView.as_view(), name='salesperson_detail'),
    
    # ========== Lead Management API ==========
    path('api/leads/', LeadListView.as_view(), name='lead_list'),
    path('api/leads/create/', LeadCreateView.as_view(), name='lead_create'),
    path('api/leads/<int:lead_id>/', LeadDetailView.as_view(), name='lead_detail'),
    path('api/leads/<int:lead_id>/assign/', LeadAssignView.as_view(), name='lead_assign'),
    
    # ========== Quotation Management API ==========
    path('api/quotations/', QuotationListView.as_view(), name='quotation_list'),
    path('api/quotations/create/', QuotationCreateView.as_view(), name='quotation_create'),
    path('api/quotations/<int:quotation_id>/', QuotationDetailView.as_view(), name='quotation_detail'),
    path('api/quotations/<int:quotation_id>/send/', QuotationSendView.as_view(), name='quotation_send'),
    path('api/quotations/<int:quotation_id>/assign/', QuotationAssignView.as_view(), name='quotation_assign'),
    path('api/quotations/<int:quotation_id>/pdf/', QuotationPDFView.as_view(), name='quotation_pdf'),
    
    # ========== Customer Management API ==========
    path('api/customers/', CustomerListView.as_view(), name='customer_list'),
    path('api/customers/create/', CustomerCreateView.as_view(), name='customer_create'),
    path('api/customers/<int:customer_id>/', CustomerDetailView.as_view(), name='customer_detail'),
    
    # ========== Product Management API ==========
    path('api/products/', ProductListView.as_view(), name='product_list'),
    path('api/products/create/', ProductCreateView.as_view(), name='product_create'),
    path('api/products/<int:product_id>/', ProductDetailView.as_view(), name='product_detail'),
    
    # ========== Dashboard Stats API ==========
    path('api/dashboard/admin/stats/', AdminDashboardStatsView.as_view(), name='admin_dashboard_stats'),
    path('api/dashboard/salesperson/stats/', SalespersonDashboardStatsView.as_view(), name='salesperson_dashboard_stats'),

    #============Terms API ==================

    path('api/terms/', TermsListView.as_view(), name='terms-list'),
    path('api/terms/create/', TermsCreateView.as_view(), name='terms-create'),
]
