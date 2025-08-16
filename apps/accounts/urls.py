from django.urls import path
from . import views
from apps.quotations.views import SalespersonDashboardView

app_name = "accounts"

urlpatterns = [
    # Admin routes
    path("admin/login/", views.admin_login, name="admin_login"),
    path("admin/create/", views.create_admin, name="create_admin"),

    # Salesperson routes
    path("salesperson/login/", views.salesperson_login, name="salesperson_login"),
    path("salesperson/dashboard/", SalespersonDashboardView.as_view(), name="salesperson_dashboard"),
    path("salesperson/quotation/update/<int:pk>/", views.update_quotation_status, name="update_quotation_status"),
    path('lead/<int:pk>/update/', views.update_lead_status, name='update_lead_status'),
    path("salesperson/logout/", views.salesperson_logout, name="salesperson_logout"),
    path("logout/", views.universal_logout, name="logout"),

]