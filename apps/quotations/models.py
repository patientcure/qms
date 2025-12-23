from decimal import Decimal
from django.conf import settings
from django.db import models, transaction
from django.db.models import Count, Q
from django.utils import timezone
from .choices import LeadStatus, QuotationStatus, ActivityAction,CATEGORY_CHOICES,UNIT_CHOICES,LeadPriority,LeadSource
from apps.quotations.utils import generate_next_quotation_number
User = settings.AUTH_USER_MODEL
from crum import get_current_user
from apps.accounts.models import User,Roles
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.accounts.models import User,Roles
from .permissions import PERMISSIONS_MAP
def get_default_permissions():
    return PERMISSIONS_MAP.copy()

class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class CompanyProfile(TimestampedModel):
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True,unique=True)
    gst_number = models.CharField(max_length=30, blank=True)
    logo = models.ImageField(upload_to='company/', blank=True, null=True)

    def __str__(self):
        return self.name

class Customer(TimestampedModel):
    name = models.CharField(max_length=255)
    title = models.CharField(max_length=100, blank=True)
    website = models.CharField(max_length=100, blank=True)
    primary_address = models.CharField(max_length=255, blank=True)
    billing_address = models.CharField(max_length=255, blank=True)
    shipping_address = models.CharField(max_length=255, blank=True)
    company_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50,unique=True)
    gst_number = models.CharField(max_length=30, blank=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True,blank=True, related_name="customers_created"
    )

    class Meta:
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['name']),
        ]   

    def __str__(self):
        return f"{self.name} ({self.company_name})" if self.company_name else self.name
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=255) 
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), null=True, blank=True)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), null=True, blank=True)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='piece',null=True,blank=True)
    weight = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    dimensions = models.CharField(max_length=100, blank=True)
    warranty_months = models.IntegerField(null=True, blank=True)
    brand = models.CharField(max_length=100, blank=True)
    is_available = models.BooleanField(default=True)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), null=True, blank=True)  # %
    active = models.BooleanField(default=True,null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    image = models.ImageField(upload_to='products/', null=True, blank=True)

    
    class Meta:
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return self.name

class TermsAndConditions(TimestampedModel):
    title = models.CharField(max_length=255)
    content_html = models.TextField()
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=255,blank=True ,null=True)

    def __str__(self):
        return self.title

class EmailTemplate(TimestampedModel):
    title = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    body_html = models.TextField()
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.title

class Lead(TimestampedModel):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="leads")
    assigned_to = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="leads"
    )
    status = models.CharField(max_length=20, choices=LeadStatus.choices, default=LeadStatus.PENDING)
    lead_source = models.CharField(max_length=20, choices=LeadSource.choices, null=True, blank=True)
    priority = models.CharField(max_length=20, choices=LeadPriority.choices, default=LeadPriority.MEDIUM)
    follow_up_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="leads_created"
    )
    quotation_id = models.IntegerField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["follow_up_date"]),
        ]

    def save(self, *args, **kwargs):
        if not self.pk and not self.created_by:  # only when creating
            user = get_current_user()
            if user and not user.is_anonymous:
                self.created_by = user
        super().save(*args, **kwargs)
    
    @staticmethod
    def get_least_loaded_salesperson():
        return (
            User.objects
            .filter(role=Roles.SALESPERSON, is_active=True)
            .annotate(num_leads=Count('leads'))
            .order_by('num_leads', 'id')
            .first()
        )

class LeadDescription(TimestampedModel):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='descriptions')
    next_date = models.DateField(null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(max_length=2000,blank=True,null=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="lead_descriptions_created"
    )
    def __str__(self):
        return f"Description for Lead {self.lead.id}"

class Quotation(TimestampedModel):
    quotation_number = models.CharField(max_length=30, unique=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="quotations")
    assigned_to = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="quotations"
    )
    terms = models.ManyToManyField(TermsAndConditions, blank=True)
    email_template = models.ForeignKey(EmailTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=QuotationStatus.choices, default=QuotationStatus.DRAFT)
    follow_up_date = models.DateField(null=True, blank=True)
    discount_type = models.CharField(
        max_length=20,
        choices=[("percentage", "Percentage"), ("amount", "Amount")],
        default="percentage",
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=10, default="INR")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tax_rate = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    additional_charge_name = models.CharField(max_length=100, blank=True, null=True, default="Additional Charges")
    additional_charge_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), blank=True, null=True)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), blank=True, null=True)
    emailed_at = models.DateTimeField(null=True, blank=True)
    lead_id = models.IntegerField(null=True, blank=True)
    has_pdf = models.BooleanField(default=False)
    file_url = models.URLField(blank=True)
    additionalNotes = models.TextField(blank=True,null=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="quotations_created"
    )

    class Meta:
        indexes = [
            models.Index(fields=["quotation_number"]),
            models.Index(fields=["status"]),
            models.Index(fields=["follow_up_date"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        creating = self._state.adding

        # Assign created_by automatically
        if creating and not self.created_by:
            user = get_current_user()
            if user and not user.is_anonymous:
                self.created_by = user

        # Generate quotation number if missing
        if creating and not self.quotation_number:
            self.quotation_number = generate_next_quotation_number()

        super().save(*args, **kwargs)

class ProductDetails(TimestampedModel):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='details')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='details')
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), null=True, blank=True)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), null=True, blank=True)  

    class Meta:
        indexes = [models.Index(fields=['product'])]

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class EmailLog(TimestampedModel):
    to_email = models.EmailField()
    subject = models.CharField(max_length=255)
    body_preview = models.TextField(blank=True)
    provider_message_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=30, default='QUEUED')  # QUEUED/SENT/FAILED
    error = models.TextField(blank=True)
    quotation = models.ForeignKey(Quotation, null=True, blank=True, on_delete=models.SET_NULL, related_name='email_logs')
    lead = models.ForeignKey(Lead, null=True, blank=True, on_delete=models.SET_NULL, related_name='email_logs')
    sent_at = models.DateTimeField(null=True, blank=True)

    def mark_sent(self, provider_message_id: str):
        self.provider_message_id = provider_message_id
        self.status = 'SENT'
        self.sent_at = timezone.now()
        self.save(update_fields=['provider_message_id', 'status', 'sent_at'])

    def mark_failed(self, error: str):
        self.status = 'FAILED'
        self.error = error[:1000]
        self.save(update_fields=['status', 'error'])

class ActivityLog(TimestampedModel):
    actor = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='activity_logs')
    customer = models.ForeignKey(Customer,on_delete=models.SET_NULL,null=True,blank=True,related_name='activity_logs')
    action = models.CharField(max_length=50, choices=ActivityAction.choices)
    entity_type = models.CharField(max_length=50)
    entity_id = models.CharField(max_length=50)
    message = models.TextField(blank=True)  

    class Meta:
        indexes = [
            models.Index(fields=['action']),
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} on {self.entity_type}({self.entity_id})"

    @classmethod
    def log(cls, actor, action, entity, customer ,message=''):
        return cls.objects.create(
            actor=actor,
            action=action,
            entity_type=entity.__class__.__name__,
            entity_id=str(getattr(entity, 'id', '')),
            message=message,
            customer = customer,
        )
    
class SalespersonPermission(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='permissions',
        limit_choices_to={'role': Roles.SALESPERSON}
    )
    permissions = models.JSONField(default=get_default_permissions, blank=True)

    def __str__(self):
        return f"Permissions for {self.user.get_full_name()}"

    class Meta:
        verbose_name = "Salesperson Permission"
        verbose_name_plural = "Salesperson Permissions"

@receiver(post_save, sender=User)
def create_salesperson_permissions(sender, instance, created, **kwargs):
    if created and instance.role == Roles.SALESPERSON:
        SalespersonPermission.objects.create(user=instance)


class ProductImage(TimestampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    quotation = models.ForeignKey(Quotation, on_delete=models.SET_NULL, null=True, blank=True, related_name='product_images')
    image = models.ImageField(upload_to='product_images/')

    def __str__(self):
        return f"Image for {self.product.name}"
    
class SignatureImage(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='signatures')
    image = models.ImageField(upload_to='signatures/')

    def __str__(self):
        return f"Signature for User {self.user.get_full_name()}"