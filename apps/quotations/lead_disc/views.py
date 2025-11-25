import json
from django.views import View
from django.http import JsonResponse
from ..models import LeadDescription, Lead

class LeadDescriptionManageView(View):

    def post(self, request, lead_id):
        try:
            body = json.loads(request.body.decode("utf-8"))
        except:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        description = body.get("description")
        next_date = body.get("next_date")

        if not description:
            return JsonResponse({"error": "Description is required"}, status=400)

        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return JsonResponse({"error": "Lead not found"}, status=404)

        ld = LeadDescription.objects.create(
            lead=lead,
            description=description,
            next_date=next_date
        )

        return JsonResponse({
            "id": ld.id,
            "description": ld.description,
            "next_date": ld.next_date,
            "created_at": ld.created_at
        }, status=201)

    def get(self, request, lead_id):
        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return JsonResponse({"error": "Lead not found"}, status=404)

        descriptions = lead.descriptions.all().order_by('-created_at')

        data = [
            {
                "id": d.id,
                "description": d.description,
                "next_date": d.next_date,
                "created_at": d.created_at,
            }
            for d in descriptions
        ]

        return JsonResponse({"descriptions": data})
