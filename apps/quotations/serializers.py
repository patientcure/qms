from rest_framework import serializers
from .models import TermsAndConditions

class TermsAndConditionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TermsAndConditions
        fields = ['id', 'title', 'content_html', 'is_default']
