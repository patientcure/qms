# accounts/urls.py
from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    # Admin
    path('admin/login/', views.admin_login, name='admin_login'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/salesperson/create/', views.create_salesperson, name='create_salesperson'),

    # Salesperson
    # path('salesperson/login/', views.salesperson_login, name='salesperson_login'),
]
