from django.contrib.auth import authenticate, login, logout, get_user_model
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test

User = get_user_model()

def is_admin(user):
    return user.role == "ADMIN"

# Admin login view
def admin_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user and user.role == "ADMIN":
            login(request, user)
            return redirect("accounts:admin_dashboard")  # namespace added
        else:
            return render(request, "accounts/admin_login.html", {"error": "Invalid credentials"})
    return render(request, "accounts/admin_login.html")

# Admin dashboard showing all salespersons
@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    salespersons = User.objects.filter(role="SALESPERSON")
    return render(request, "accounts/admin_dashboard.html", {"salespersons": salespersons})

# Create salesperson
@login_required
@user_passes_test(is_admin)
def create_salesperson(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        if username and password and email:
            User.objects.create_user(username=username, email=email, password=password, role="SALESPERSON")
            return redirect("accounts:admin_dashboard")  # namespace added
    return render(request, "accounts/create_salesperson.html")

# Enable/disable salesperson
@login_required
@user_passes_test(is_admin)
def toggle_salesperson(request, user_id):
    salesperson = get_object_or_404(User, id=user_id, role="SALESPERSON")
    salesperson.is_active = not salesperson.is_active
    salesperson.save()
    return redirect("accounts:admin_dashboard")  # namespace added

# Salesperson login
def salesperson_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user and user.role == "SALESPERSON":
            login(request, user)
            return redirect("accounts:salesperson_dashboard")  # namespace added
        else:
            return render(request, "accounts/salesperson_login.html", {"error": "Invalid credentials"})
    return render(request, "accounts/salesperson_login.html")

# Salesperson dashboard
@login_required
def salesperson_dashboard(request):
    return render(request, "accounts/salesperson_dashboard.html")

def create_admin(request):
    # Only allow if no admin exists
    # if User.objects.filter(role="ADMIN").exists():
    #     return redirect("accounts:admin_dashboard")

    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        if username and email and password:
            User.objects.create_user(username=username, email=email, password=password, role="ADMIN")
            return redirect("accounts:admin_login")
    return render(request, "accounts/create_admin.html")

def salesperson_logout(request):
    logout(request)
    return redirect("accounts:salesperson_login")