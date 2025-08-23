from django.contrib import admin
from .models import CompanyProfile, Customer, Product, TermsAndConditions, EmailTemplate, Lead, Quotation, QuotationItem, EmailLog, ActivityLog

@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone')

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'company_name', 'email', 'phone')
    search_fields = ('name', 'company_name', 'email')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name',  'tax_rate', 'active')
    list_filter = ('active',)
    search_fields = ('name', 'sku')

@admin.register(TermsAndConditions)
class TnCAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_default', 'updated_at')

@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'is_default', 'updated_at')

class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 1

@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ('quotation_number', 'customer', 'assigned_to', 'status', 'total', 'follow_up_date', 'created_at')
    list_filter = ('status', 'assigned_to', 'created_at', 'follow_up_date')
    search_fields = ('quotation_number', 'customer__name', 'customer__email')
    inlines = [QuotationItemInline]

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'assigned_to', 'status', 'follow_up_date', 'created_at')
    list_filter = ('status', 'assigned_to')

@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ('to_email', 'subject', 'status', 'sent_at', 'quotation')
    list_filter = ('status',)
    search_fields = ('to_email', 'subject', 'provider_message_id')

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'entity_type', 'entity_id', 'actor', 'created_at')
    list_filter = ('action', 'entity_type')
    search_fields = ('message',)