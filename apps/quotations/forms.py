from django import forms
from .models import Customer, Product, Quotation, QuotationItem, TermsAndConditions, EmailTemplate

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "company_name", "email", "phone", "address", "gst_number"]

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "sku", "description", "unit_price", "tax_rate", "active"]

class QuotationItemForm(forms.ModelForm):
    class Meta:
        model = QuotationItem
        fields = ["product", "description", "quantity", "unit_price", "tax_rate"]

QuotationItemFormSet = forms.inlineformset_factory(
    Quotation,
    QuotationItem,
    form=QuotationItemForm,
    extra=1,
    can_delete=True,
)

class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = ["customer", "assigned_to", "terms", "email_template", "follow_up_date", "currency"]
        widgets = {
            "follow_up_date": forms.DateInput(attrs={"type": "date"})
        }
