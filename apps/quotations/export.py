import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Product, Quotation, Lead

@require_POST
def get_all_entities_fields(request):
    try:
        data = json.loads(request.body)
        entity_type = data.get('entity', '').lower()
        requested_fields = data.get('fields', [])
        from_date = data.get('from_date')
        to_date = data.get('to_date')
        model_map = {
            'product': Product,
            'quotation': Quotation,
            'lead': Lead
        }

        if entity_type not in model_map:
            return JsonResponse({'error': 'Invalid entity type'}, status=400)

        model = model_map[entity_type]
        queryset = model.objects.all()
        if from_date and to_date:
            queryset = queryset.filter(created_at__range=[from_date, to_date])
        non_relational_field_names = [
            f.name for f in model._meta.get_fields() 
            if not f.is_relation
        ]
        valid_fields = ['id']
        for field in requested_fields:
            if field in non_relational_field_names:
                valid_fields.append(field)
        results = list(queryset.values(*valid_fields))

        return JsonResponse({
            'entity': entity_type,
            'count': len(results),
            'results': results
        }, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)