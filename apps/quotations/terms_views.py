from rest_framework import generics
from .models import TermsAndConditions
from .serializers import TermsAndConditionsSerializer

# List all terms
class TermsListView(generics.ListAPIView):
    queryset = TermsAndConditions.objects.all()
    serializer_class = TermsAndConditionsSerializer
    # permission_classes = [IsAuthenticated]

class TermsCreateView(generics.CreateAPIView):
    queryset = TermsAndConditions.objects.all()
    serializer_class = TermsAndConditionsSerializer

class TermDeleteView(generics.DestroyAPIView):
    queryset = TermsAndConditions.objects.all()
    serializer_class = TermsAndConditionsSerializer
    lookup_field = 'id'

class TermUpdateView(generics.UpdateAPIView):
    queryset = TermsAndConditions.objects.all()
    serializer_class = TermsAndConditionsSerializer
    lookup_field = 'id'