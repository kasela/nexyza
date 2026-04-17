from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import BrandingConfig


@login_required
def branding_settings(request):
    branding, _ = BrandingConfig.objects.get_or_create(user=request.user)
    color_fields = [
        ('primary_color', 'Primary Color',  '#7c3aed'),
        ('accent_color',  'Accent Color',   '#3b82f6'),
        ('bg_color',      'Background',     '#0d0b17'),
        ('surface_color', 'Surface/Card',   '#1e1b2e'),
    ]
    return render(request, 'whitelabel/settings.html', {
        'branding': branding,
        'color_fields': color_fields,
    })


@login_required
@require_POST
def save_branding(request):
    branding, _ = BrandingConfig.objects.get_or_create(user=request.user)
    branding.app_name       = request.POST.get('app_name', 'Nexyza')[:60]
    branding.primary_color  = request.POST.get('primary_color', '#7c3aed')
    branding.accent_color   = request.POST.get('accent_color', '#3b82f6')
    branding.bg_color       = request.POST.get('bg_color', '#0d0b17')
    branding.surface_color  = request.POST.get('surface_color', '#1e1b2e')
    branding.custom_css     = request.POST.get('custom_css', '')[:5000]
    branding.hide_datalens_branding = request.POST.get('hide_branding') == 'on'
    branding.custom_domain  = request.POST.get('custom_domain', '')[:253]

    if 'logo' in request.FILES:
        branding.logo = request.FILES['logo']
    if 'favicon' in request.FILES:
        branding.favicon = request.FILES['favicon']

    branding.save()
    messages.success(request, 'Branding saved.')
    return redirect('whitelabel:settings')


@login_required
@require_POST
def reset_branding(request):
    BrandingConfig.objects.filter(user=request.user).delete()
    messages.success(request, 'Branding reset to defaults.')
    return redirect('whitelabel:settings')
