# accounts/views.py
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse

# Helper to check if user is admin

def is_admin(user):
    return user.is_superuser

# Admin login view
def admin_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user and user.is_superuser:
            login(request, user)
            return redirect("admin_dashboard")
        else:
            return render(request, "accounts/admin_login.html", {"error": "Invalid credentials"})
    return render(request, "accounts/admin_login.html")

# Admin dashboard showing all salespersons
@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    salespersons = User.objects.filter(is_superuser=False)
    return render(request, "accounts/admin_dashboard.html", {"salespersons": salespersons})

# Create salesperson
@login_required
@user_passes_test(is_admin)
def create_salesperson(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        if username and password:
            User.objects.create_user(username=username, password=password)
            return redirect("admin_dashboard")
    return render(request, "accounts/create_salesperson.html")

# Enable/disable salesperson
@login_required
@user_passes_test(is_admin)
def toggle_salesperson(request, user_id):
    salesperson = get_object_or_404(User, id=user_id, is_superuser=False)
    salesperson.is_active = not salesperson.is_active
    salesperson.save()
    return redirect("admin_dashboard")
