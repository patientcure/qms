from django.urls import path
from .views import (
    AdminLoginView,
    SalespersonLoginView,
    CreateAdminView,
    LogoutView,
    CurrentUserView,
    QuotationStatusUpdateView,
    LeadStatusUpdateView,
)

app_name = "accounts"

urlpatterns = [
    # ========== Authentication API ==========
    path("api/admin/login/", AdminLoginView.as_view(), name="admin_login"),
    path("api/salesperson/login/", SalespersonLoginView.as_view(), name="salesperson_login"),
    path("api/admin/create/", CreateAdminView.as_view(), name="create_admin"),
    path("api/logout/", LogoutView.as_view(), name="logout"),
    path("api/user/current/", CurrentUserView.as_view(), name="current_user"),
    
    # ========== Status Update API ==========
    path("api/quotations/<int:quotation_id>/status/", QuotationStatusUpdateView.as_view(), name="update_quotation_status"),
    path("api/leads/<int:lead_id>/status/", LeadStatusUpdateView.as_view(), name="update_lead_status"),
]