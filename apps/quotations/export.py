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
        model_map = {
            'product': Product,
            'quotation': Quotation,
            'lead': Lead
        }

        if entity_type not in model_map:
            return JsonResponse({'error': 'Invalid entity type. Use product, quotation, or lead.'}, status=400)

        model = model_map[entity_type]
        valid_fields = ['id']
        model_field_names = [f.name for f in model._meta.get_fields()]
        
        for field in requested_fields:
            if field in model_field_names:
                valid_fields.append(field)
        entities_data = list(model.objects.all().values(*valid_fields))

        return JsonResponse({
            'entity': entity_type,
            'count': len(entities_data),
            'results': entities_data
        }, safe=False)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)