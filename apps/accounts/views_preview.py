from django.shortcuts import render
from django.views import View

class StaticHTMLPreview(View):
    def get(self, request, template_name):
        return render(request, template_name)
