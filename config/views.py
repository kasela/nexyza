
from django.shortcuts import render

def handler_404(request, exception):
    return render(request, '404.html', status=404)

def handler_500(request):
    return render(request, '500.html', status=500)
