# urls.py - Complete URL configuration

from django.urls import path
from .terms_views import (
    TermsListView,
    TermsCreateView,
    TermDeleteView,
    TermUpdateView
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
    CategoryViewSet,
    
    # Dashboard Stats
    AdminDashboardStatsView,
    SalespersonDashboardStatsView,
    # Product & Customer Search
    ProductSearchView,
    CustomerSearchView,


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
    
    # ========== Product Management API ==========
    path('api/products/', ProductListView.as_view(), name='product_list'),
    path('api/products/create/', ProductCreateView.as_view(), name='product_create'),
    path('api/products/<int:product_id>/', ProductDetailView.as_view(), name='product_detail'),
    path('api/products/search/', ProductSearchView.as_view(), name='product_search'),

    # ========== NEW URLS FOR CATEGORY VIEWSET ==========
    # This single path handles both GET (to list) and POST (to create)
    path('api/categories/', CategoryViewSet.as_view({'get': 'list', 'post': 'create'}), name='category-list-create'),
    
    # This single path handles GET (one), PUT/PATCH (update), and DELETE
    path('api/categories/<int:pk>/', CategoryViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='category-detail'),
    # =================================================

    # ========== Customer Management API ==========
    path('api/customers/', CustomerListView.as_view(), name='customer_list'),
    path('api/customers/create/', CustomerCreateView.as_view(), name='customer_create'),
    path('api/customers/<int:customer_id>/', CustomerDetailView.as_view(), name='customer_detail'),
    path('api/customers/search/', CustomerSearchView.as_view(), name='customer_search'),
    
    # ========== Dashboard Stats API ==========
    path('api/dashboard/admin/stats/', AdminDashboardStatsView.as_view(), name='admin_dashboard_stats'),
    path('api/dashboard/salesperson/stats/', SalespersonDashboardStatsView.as_view(), name='salesperson_dashboard_stats'),

    #============Terms API ==================
    path('api/terms/', TermsListView.as_view(), name='terms-list'),
    path('api/terms/create/', TermsCreateView.as_view(), name='terms-create'),
    path('api/terms/<int:id>/update/', TermUpdateView.as_view(), name='terms-update'),
    path('api/terms/<int:id>/delete/', TermDeleteView.as_view(), name='terms-delete'),
]