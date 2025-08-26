from django import forms
from .models import Customer, Product, Quotation, TermsAndConditions, EmailTemplate
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from .models import Lead, Customer
from apps.accounts.models import User,Roles

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["id","name", "company_name", "email", "phone", "address", "gst_number","title","website","primary_address","billing_address","shipping_address"]

class ProductForm(forms.ModelForm):
    discount = forms.DecimalField(required=False, max_digits=10, decimal_places=2, initial=0)
    class Meta:
        model = Product
        fields = [
            "name", "description", "category", "cost_price", 
            "selling_price", "tax_rate", "unit", "weight", 
            "dimensions", "warranty_months", "brand", "is_available", "active"
        ]
# class QuotationItemForm(forms.ModelForm):
#     class Meta:
#         model = QuotationItem
#         fields = ["product", "description", "quantity", "unit_price", "tax_rate"]

# QuotationItemFormSet = forms.inlineformset_factory(
#     Quotation,
#     QuotationItem,
#     form=QuotationItemForm,
#     extra=1,
#     can_delete=True,
# )

class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = [
            'customer', 'assigned_to', 'terms', 'email_template', 'discount',
            'follow_up_date','status'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_to'].required = False
        self.fields['terms'].required = False
        self.fields['email_template'].required = False
        self.fields['follow_up_date'].required = False
        self.fields['status'].required = False
        
class SalespersonForm(UserCreationForm):
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    email = forms.EmailField(required=True)
    phone = forms.CharField(required=False)
    is_active = forms.BooleanField(initial=True, required=False)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'phone', 'is_active', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        self.password_required = kwargs.pop('password_required', True)
        super().__init__(*args, **kwargs)
        
        if not self.password_required:
            self.fields['password1'].required = False
            self.fields['password2'].required = False
            self.fields['password1'].widget.attrs['placeholder'] = 'Leave blank to keep current password'
            self.fields['password2'].widget.attrs['placeholder'] = 'Leave blank to keep current password'

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email
    
    
class LeadForm(forms.ModelForm):
    customer_name = forms.CharField(required=True)
    customer_email = forms.EmailField(required=True)
    customer_phone = forms.CharField(required=True)
    customer_company = forms.CharField(required=False)
    customer_primary_address = forms.CharField(required=False)
    customer_billing_address = forms.CharField(required=False)
    customer_shipping_address = forms.CharField(required=False)

    class Meta:
        model = Lead
        fields = [
            'customer_name', 'customer_email', 'customer_phone', 'customer_company',
            'customer_primary_address', 'customer_billing_address', 'customer_shipping_address',
            'status', 'source', 'follow_up_date', 'notes', 'assigned_to'
        ]
        widgets = {
            'follow_up_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_to'].queryset = User.objects.filter(role=Roles.SALESPERSON)
        if customer := getattr(self.instance, "customer", None):
            mapping = {
                'name': 'customer_name',
                'email': 'customer_email',
                'phone': 'customer_phone',
                'company_name': 'customer_company',
                'primary_address': 'customer_primary_address',
                'billing_address': 'customer_billing_address',
                'shipping_address': 'customer_shipping_address',
            }
            for attr, field_name in mapping.items():
                self.fields[field_name].initial = getattr(customer, attr, '')

    def clean(self):
        cleaned_data = super().clean()
        customer_data = {
            'name': cleaned_data.get('customer_name'),
            'email': cleaned_data.get('customer_email'),
            'phone': cleaned_data.get('customer_phone'),
            'company_name': cleaned_data.get('customer_company'),
            'primary_address': cleaned_data.get('customer_primary_address'),
            'billing_address': cleaned_data.get('customer_billing_address'),
            'shipping_address': cleaned_data.get('customer_shipping_address'),
        }
        customer, _ = Customer.objects.update_or_create(
            email=customer_data['phone'],
            defaults=customer_data
        )

        cleaned_data['customer'] = customer
        return cleaned_data

    def save(self, commit=True):
        lead = super().save(commit=False)
        lead.customer = self.cleaned_data['customer']
        if commit:
            lead.save()
        return lead


    def clean(self):
        cleaned_data = super().clean()
        customer_email = cleaned_data.get('customer_email')
        
        customer, created = Customer.objects.get_or_create(
            email=customer_email,
            defaults={
                'name': cleaned_data.get('customer_name'),
                'phone': cleaned_data.get('customer_phone'),
                'company_name': cleaned_data.get('customer_company'),
            }
        )
        
        if not created:
            update_fields = {}
            if customer.name != cleaned_data.get('customer_name'):
                update_fields['name'] = cleaned_data.get('customer_name')
            if customer.phone != cleaned_data.get('customer_phone'):
                update_fields['phone'] = cleaned_data.get('customer_phone')
            if customer.company_name != cleaned_data.get('customer_company'):
                update_fields['company_name'] = cleaned_data.get('customer_company')
            
            if update_fields:
                Customer.objects.filter(pk=customer.pk).update(**update_fields)
                customer.refresh_from_db()
        
        cleaned_data['customer'] = customer
        return cleaned_data

    def save(self, commit=True):
        lead = super().save(commit=False)
        lead.customer = self.cleaned_data['customer']
        
        if commit:
            lead.save()
        return lead
    

