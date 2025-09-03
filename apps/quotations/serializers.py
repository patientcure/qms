from rest_framework import serializers
from .models import TermsAndConditions,Category

class TermsAndConditionsSerializer(serializers.ModelSerializer):
    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user.get_full_name() or request.user.username
        return super().create(validated_data)
    class Meta:
        model = TermsAndConditions
        fields = ['id', 'title', 'content_html', 'is_default', 'created_at', 'created_by']

        
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description']
