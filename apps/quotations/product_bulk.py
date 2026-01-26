from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Product
from rest_framework import serializers

class ProductCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'name', 'description', 'cost_price', 'selling_price', 
            'unit', 'weight', 'dimensions', 'warranty_months', 
            'brand', 'is_available', 'discount', 'active'
        ]

class BulkProductUploadView(APIView):
    def post(self, request, *args, **kwargs):
        data = request.data
        
        if not isinstance(data, list):
            return Response(
                {"error": "Expected a list of items"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        success_objects = []
        errors = []
        
        for index, item in enumerate(data):
            serializer = ProductCreateSerializer(data=item)
            if serializer.is_valid():
                success_objects.append(Product(**serializer.validated_data))
            else:
                errors.append({
                    "row_index": index,
                    "errors": serializer.errors,
                    "data": item
                })

        created_count = 0
        if success_objects:
            created_products = Product.objects.bulk_create(success_objects)
            created_count = len(created_products)

        return Response({
            "message": f"Successfully created {created_count} products.",
            "failed_count": len(errors),
            "errors": errors
        }, status=status.HTTP_207_MULTI_STATUS if errors else status.HTTP_201_CREATED)