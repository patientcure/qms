from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    # Admin
    path("admin/login/", views.admin_login, name="admin_login"),
    path("admin/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin/salesperson/create/", views.create_salesperson, name="create_salesperson"),
    path("admin/salesperson/toggle/<int:user_id>/", views.toggle_salesperson, name="toggle_salesperson"),
    path("admin/create/", views.create_admin, name="create_admin"),
    # Salesperson
    path("salesperson/login/", views.salesperson_login, name="salesperson_login"),
    path("salesperson/dashboard/", views.salesperson_dashboard, name="salesperson_dashboard"),
    path("salesperson/logout/", views.salesperson_logout, name="salesperson_logout"), 
]
