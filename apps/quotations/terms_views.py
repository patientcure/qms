from rest_framework import generics
from rest_framework.permissions import IsAuthenticated 
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
    # permission_classes = [IsAuthenticated]

