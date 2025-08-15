from django.db import models

class LeadStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    COMPLETED = 'COMPLETED', 'Completed'
    CANCELLED = 'CANCELLED', 'Cancelled'

class QuotationStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'            # created but not mailed
    MAIL_SENT = 'MAIL_SENT', 'Mail Sent'      # automatically set after email send
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    COMPLETED = 'COMPLETED', 'Completed'
    CANCELLED = 'CANCELLED', 'Cancelled'

class ActivityAction(models.TextChoices):
    LOGIN = 'LOGIN', 'Login'
    LEAD_CREATED = 'LEAD_CREATED', 'Lead Created'
    LEAD_ASSIGNED = 'LEAD_ASSIGNED', 'Lead Assigned'
    LEAD_STATUS_UPDATED = 'LEAD_STATUS_UPDATED', 'Lead Status Updated'
    QUOTATION_CREATED = 'QUOTATION_CREATED', 'Quotation Created'
    QUOTATION_UPDATED = 'QUOTATION_UPDATED', 'Quotation Updated'
    QUOTATION_SENT = 'QUOTATION_SENT', 'Quotation Sent'
    QUOTATION_STATUS_UPDATED = 'QUOTATION_STATUS_UPDATED', 'Quotation Status Updated'
    FILE_UPLOADED = 'FILE_UPLOADED', 'File Uploaded'
    EMAIL_SENT = 'EMAIL_SENT', 'Email Sent'
    EMAIL_FAILED = 'EMAIL_FAILED', 'Email Failed'