from django.urls import path
from . import views
from .views import (
    AdminDashboardView,
    CreateSalespersonView,
    EditSalespersonView,
    ToggleSalespersonStatusView,
    CreateLeadView,
    EditLeadView,
    AssignLeadView,
    AdminQuotationCreateView,
    GetProductDetailsView,

)

app_name = "quotations"

urlpatterns = [
    path("create/", views.QuotationCreateView.as_view(), name="create"),
    path("preview/<int:pk>/", views.QuotationPreviewView.as_view(), name="preview"),
    path("send/<int:pk>/", views.QuotationSendView.as_view(), name="send"),
    path("list/", views.QuotationListView.as_view(), name="list"),
    path("export.csv", views.QuotationCSVExportView.as_view(), name="export_csv"),
    path("dashboard/", views.SalespersonDashboardView.as_view(), name="dashboard"),
    path('admin/', AdminDashboardView.as_view(), name='admin_dashboard'),
    
    # Salesperson management
    path('salespeople/create/', CreateSalespersonView.as_view(), name='create_salesperson'),
    path('salespeople/<int:user_id>/edit/', EditSalespersonView.as_view(), name='edit_salesperson'),
    path('salespeople/<int:user_id>/toggle-status/', ToggleSalespersonStatusView.as_view(), name='toggle_salesperson_status'),
    
    # Lead management
    path('leads/create/', CreateLeadView.as_view(), name='create_lead'),
    path('leads/<int:lead_id>/edit/', EditLeadView.as_view(), name='edit_lead'),
    path('leads/<int:lead_id>/assign/', AssignLeadView.as_view(), name='assign_lead'),
    
    # Quotation
    path('quotations/create/', AdminQuotationCreateView.as_view(), name='admin_create_quotation'),
    
    # AJAX
    path('ajax/products/<int:product_id>/', GetProductDetailsView.as_view(), name='get_product_details'),
    
    # modal add-new endpoints
    path("ajax/customer/new/", views.CustomerCreateAjaxView.as_view(), name="ajax_customer_new"),
    path("ajax/product/new/", views.ProductCreateAjaxView.as_view(), name="ajax_product_new"),
    path('ajax/live-preview/', views.QuotationLivePreviewView.as_view(), name='ajax_live_preview'),
]
