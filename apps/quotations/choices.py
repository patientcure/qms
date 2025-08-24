from django.db import models
from django.utils.translation import gettext_lazy as _


class LeadStatus(models.TextChoices):
    PENDING = 'PENDING', _('Pending')
    IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
    CONVERTED = 'CONVERTED', _('Converted')
    LOST = 'LOST', _('Lost')
    ON_HOLD = 'ON_HOLD', _('On Hold')

class QuotationStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    PENDING = 'PENDING', 'Pending'
    SENT = 'SENT', 'Sent'
    ACCEPTED = 'ACCEPTED', 'Accepted'
    REJECTED = 'REJECTED', 'Rejected'
    EXPIRED = 'EXPIRED', 'Expired'
class ActivityAction(models.TextChoices):
    # User actions
    LOGIN = 'LOGIN', _('User Login')
    LOGOUT = 'LOGOUT', _('User Logout')
    PASSWORD_CHANGE = 'PASSWORD_CHANGE', _('Password Changed')
    
    # Customer actions
    CUSTOMER_CREATED = 'CUSTOMER_CREATED', _('Customer Created')
    CUSTOMER_UPDATED = 'CUSTOMER_UPDATED', _('Customer Updated')
    
    # Lead actions
    LEAD_CREATED = 'LEAD_CREATED', _('Lead Created')
    LEAD_UPDATED = 'LEAD_UPDATED', _('Lead Updated')
    LEAD_ASSIGNED = 'LEAD_ASSIGNED', _('Lead Assigned')
    LEAD_STATUS_CHANGED = 'LEAD_STATUS_CHANGED', _('Lead Status Changed')
    
    # Quotation actions
    QUOTATION_CREATED = 'QUOTATION_CREATED', _('Quotation Created')
    QUOTATION_UPDATED = 'QUOTATION_UPDATED', _('Quotation Updated')
    QUOTATION_STATUS_CHANGED = 'QUOTATION_STATUS_CHANGED', _('Quotation Status Changed')
    QUOTATION_SENT = 'QUOTATION_SENT', _('Quotation Sent')
    QUOTATION_VIEWED = 'QUOTATION_VIEWED', _('Quotation Viewed by Customer')
    
    # Product actions
    PRODUCT_CREATED = 'PRODUCT_CREATED', _('Product Created')
    PRODUCT_UPDATED = 'PRODUCT_UPDATED', _('Product Updated')
    
    # System actions
    SYSTEM_NOTIFICATION = 'SYSTEM_NOTIFICATION', _('System Notification')

class Currency(models.TextChoices):
    INR = 'INR', _('Indian Rupee (₹)')
    USD = 'USD', _('US Dollar ($)')
    EUR = 'EUR', _('Euro (€)')
    GBP = 'GBP', _('British Pound (£)')
    AED = 'AED', _('UAE Dirham (د.إ)')
    SAR = 'SAR', _('Saudi Riyal (﷼)')

class TaxType(models.TextChoices):
    GST = 'GST', _('GST')
    VAT = 'VAT', _('VAT')
    IGST = 'IGST', _('IGST')
    CGST = 'CGST', _('CGST')
    SGST = 'SGST', _('SGST')
    NONE = 'NONE', _('No Tax')

class LeadSource(models.TextChoices):
    WEBSITE = 'WEBSITE', _('Website')
    REFERRAL = 'REFERRAL', _('Referral')
    SOCIAL_MEDIA = 'SOCIAL_MEDIA', _('Social Media')
    EMAIL = 'EMAIL', _('Email Campaign')
    COLD_CALL = 'COLD_CALL', _('Cold Call')
    EXHIBITION = 'EXHIBITION', _('Exhibition/Trade Show')
    EXISTING_CUSTOMER = 'EXISTING_CUSTOMER', _('Existing Customer')
    OTHER = 'OTHER', _('Other')

class Priority(models.TextChoices):
    LOW = 'LOW', _('Low')
    MEDIUM = 'MEDIUM', _('Medium')
    HIGH = 'HIGH', _('High')
    URGENT = 'URGENT', _('Urgent')

class NotificationType(models.TextChoices):
    LEAD_ASSIGNMENT = 'LEAD_ASSIGNMENT', _('Lead Assignment')
    QUOTATION_ASSIGNMENT = 'QUOTATION_ASSIGNMENT', _('Quotation Assignment')
    FOLLOW_UP_REMINDER = 'FOLLOW_UP_REMINDER', _('Follow-up Reminder')
    QUOTATION_EXPIRY = 'QUOTATION_EXPIRY', _('Quotation Expiry')
    SYSTEM_ALERT = 'SYSTEM_ALERT', _('System Alert')

CATEGORY_CHOICES = [
('hardware', 'Hardware'),
('software', 'Software'),
('electronics', 'Electronics'),
('accessories', 'Accessories'),
]
UNIT_CHOICES = [
('piece', 'Piece'),
('kg', 'Kilogram'),
('liter', 'Liter'),
('meter', 'Meter'),
]