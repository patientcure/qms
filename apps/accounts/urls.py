from django.urls import path
from .views import (
    AdminLoginView,
    SalespersonLoginView,
    CreateUserView,
    LogoutView,
    CurrentUserView,
    QuotationStatusUpdateView,
    LeadStatusUpdateView,
    UserListView,
    DeleteUserView,
    ToggleUserType,
    ChangePasswordView,
    CheckTokenValidityView,
    EditUserView
)

app_name = "accounts"

urlpatterns = [
    # ========== Authentication API ==========
    path("api/staff/login/", AdminLoginView.as_view(), name="admin_login"),
    path("api/salesperson/login/", SalespersonLoginView.as_view(), name="salesperson_login"),
    path("api/admin/create/", CreateUserView.as_view(), name="create_admin"),
    path("api/logout/", LogoutView.as_view(), name="logout"),
    path("api/user/current/", CurrentUserView.as_view(), name="current_user"),
    path("api/users/", UserListView.as_view(), name="user_list"),
    path("api/users/<int:user_id>/delete/", DeleteUserView.as_view(), name="delete_user"),
    path("api/token/verify/", CheckTokenValidityView.as_view(), name="check_token_validity"),


    # ========== Password Management API ==========
    path("api/user/change-password/", ChangePasswordView.as_view(), name="change_password"),

    
    # ========== Status Update API ==========
    path("api/quotations/<int:quotation_id>/status/", QuotationStatusUpdateView.as_view(), name="update_quotation_status"),
    path("api/leads/<int:lead_id>/status/", LeadStatusUpdateView.as_view(), name="update_lead_status"),

    path("api/<int:user_id>/toggleUser/",ToggleUserType.as_view(),name="toggle_user"),
    path("api/users/<int:user_id>/edit/", EditUserView.as_view(), name="edit_user")

]