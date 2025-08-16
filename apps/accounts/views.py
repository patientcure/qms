from django.contrib.auth import authenticate, login, logout, get_user_model
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponseBadRequest
from apps.quotations.models import Quotation,ActivityAction, ActivityLog,QuotationStatus
from django.views.decorators.http import require_POST
from django.contrib import messages
from datetime import datetime


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
            return redirect("quotations:admin_dashboard")  # namespace added
        else:
            return render(request, "accounts/admin_login.html", {"error": "Invalid credentials"})
    return render(request, "accounts/admin_login.html")



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

def universal_logout(request):
    user_role = getattr(request.user, 'role', None)
    logout(request)
    if user_role == "ADMIN":
        return redirect("accounts:admin_login")
    else:
        return redirect("accounts:salesperson_login")



@login_required
@require_POST
def update_quotation_status(request, pk):
    if request.method == "POST":
        quotation = get_object_or_404(Quotation, pk=pk)
        changes = []

        # Update status
        status = request.POST.get("status")
        if status in dict(QuotationStatus.choices) and status != quotation.status:
            old_status = quotation.status
            quotation.status = status
            changes.append(f"Status changed from {old_status} to {status}")

        # Update follow-up date
        follow_up_date_str = request.POST.get("follow_up_date")
        if follow_up_date_str:
            try:
                new_date = datetime.strptime(follow_up_date_str, "%Y-%m-%d").date()
                if quotation.follow_up_date != new_date:
                    old_date = quotation.follow_up_date
                    quotation.follow_up_date = new_date
                    changes.append(f"Follow-up date changed from {old_date} to {new_date}")
            except ValueError:
                messages.error(request, "Invalid follow-up date format. Use YYYY-MM-DD.")
                return redirect(request.META.get('HTTP_REFERER', '/'))

        quotation.save(update_fields=['status', 'follow_up_date'])

        if changes:
            message = "; ".join(changes)
            ActivityLog.log(
                actor=request.user,
                action=ActivityAction.QUOTATION_UPDATED,
                entity=quotation,
                message=message
            )

        messages.success(request, "Quotation updated successfully.")
        return redirect(request.META.get('HTTP_REFERER', '/'))

    messages.error(request, "Invalid request method.")
    return redirect(request.META.get('HTTP_REFERER', '/'))