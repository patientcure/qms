# urls.py - Complete URL configuration

from django.urls import path
from .terms_views import (
    TermsListView,
    TermsCreateView,
    TermDeleteView,
    TermUpdateView
)
from .duplicate import DuplicateQuotationAPIView
from .quotation_create import QuotationCreate
from .merge_pdf import MergePDFsAPIView
from .product_image_view import ProductImageUploadView
from .product_create_view import ProductCreateView
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
    AllCustomerListView,
    
    # Product Management
    ProductListView,
    ProductDetailView,
    CategoryViewSet,
    
    # Dashboard Stats
    AdminDashboardStatsView,
    SalespersonDashboardStatsView,
    TopPerfomerView,
    # Product & Customer Search
    ProductSearchView,
    CustomerSearchView,
    FilteredCustomerListView,
    UnfilteredCustomerListView,
    UserStatsView
)
from .lead_disc.views import LeadDescriptionManageView


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

    # ============ Lead Description Management API ==========
    path('api/leads/<int:lead_id>/descriptions/', LeadDescriptionManageView.as_view(), name='lead_description_manage'), 
    
    # ========== Quotation Management API ==========
    path('api/quotations/', QuotationListView.as_view(), name='quotation_list'),
    path('api/quotations/create/', QuotationCreate.as_view(), name='quotation_create'),
    path('api/quotations/<int:quotation_id>/', QuotationDetailView.as_view(), name='quotation_detail'),
    path('api/quotations/<int:quotation_id>/send/', QuotationSendView.as_view(), name='quotation_send'),
    path('api/quotations/<int:quotation_id>/assign/', QuotationAssignView.as_view(), name='quotation_assign'),
    path('api/quotations/<int:quotation_id>/pdf/', QuotationPDFView.as_view(), name='quotation_pdf'),
    path('api/quotations/<int:pk>/duplicate/', DuplicateQuotationAPIView.as_view(), name='quotation_duplicate'),
    
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
    path('api/customers/all/', AllCustomerListView.as_view(), name='all_customer_list'),
    path('api/customers/create/', CustomerCreateView.as_view(), name='customer_create'),
    path('api/customers/<int:customer_id>/', CustomerDetailView.as_view(), name='customer_detail'),
    path('api/customers/search/', CustomerSearchView.as_view(), name='customer_search'),
    path('api/customers/filtered/', FilteredCustomerListView.as_view(), name='customer_filtered_list'),
    path('api/customers/unfiltered/', UnfilteredCustomerListView.as_view(), name='customer_unfiltered_list'),
    # ========== Dashboard Stats API ==========
    path('api/dashboard/admin/stats/', AdminDashboardStatsView.as_view(), name='admin_dashboard_stats'),
    path('api/dashboard/salesperson/stats/', SalespersonDashboardStatsView.as_view(), name='salesperson_dashboard_stats'),
    path('stats/top-performers/', TopPerfomerView.as_view(), name='top-performers'),

    #============Terms API ==================
    path('api/terms/', TermsListView.as_view(), name='terms-list'),
    path('api/terms/create/', TermsCreateView.as_view(), name='terms-create'),
    path('api/terms/<int:id>/update/', TermUpdateView.as_view(), name='terms-update'),
    path('api/terms/<int:id>/delete/', TermDeleteView.as_view(), name='terms-delete'),
    path('api/merge/', MergePDFsAPIView.as_view(), name='merge_pdfs'),
    path('api/<int:user_id>/stats/',UserStatsView.as_view(),name="user-stats"),
    path('api/product/image/', ProductImageUploadView.as_view(), name='product_image_upload'),
]