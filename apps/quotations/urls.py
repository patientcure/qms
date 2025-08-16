from django.urls import path
from . import views

app_name = "quotations"

urlpatterns = [
    path("create/", views.QuotationCreateView.as_view(), name="create"),
    path("preview/<int:pk>/", views.QuotationPreviewView.as_view(), name="preview"),
    path("send/<int:pk>/", views.QuotationSendView.as_view(), name="send"),
    path("list/", views.QuotationListView.as_view(), name="list"),
    path("export.csv", views.QuotationCSVExportView.as_view(), name="export_csv"),
    path("dashboard/", views.SalesDashboardView.as_view(), name="dashboard"),

    # modal add-new endpoints
    path("ajax/customer/new/", views.CustomerCreateAjaxView.as_view(), name="ajax_customer_new"),
    path("ajax/product/new/", views.ProductCreateAjaxView.as_view(), name="ajax_product_new"),
    path('ajax/live-preview/', views.QuotationLivePreviewView.as_view(), name='ajax_live_preview'),
]
