from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db.models import Q
from apps.analyser.models import FileUpload
from .models import DataAsset, LineageEdge


@login_required
def catalog_home(request):
    q      = request.GET.get('q', '')
    domain = request.GET.get('domain', '')
    source = request.GET.get('source', '')

    assets = DataAsset.objects.filter(owner=request.user).select_related('upload')
    if q:
        assets = assets.filter(Q(name__icontains=q) | Q(description__icontains=q) | Q(tags__icontains=q))
    if domain:
        assets = assets.filter(domain=domain)
    if source:
        assets = assets.filter(source_type=source)

    # Auto-create catalog entries for uploads without one
    for upload in FileUpload.objects.filter(user=request.user, status='done').exclude(catalog_entry__isnull=False)[:50]:
        asset = DataAsset.objects.create(
            upload=upload, owner=request.user,
            name=upload.original_name,
            source_type=DataAsset.SOURCE_UPLOAD,
        )
        asset.quality_score = asset.compute_quality_score()
        asset.save(update_fields=['quality_score'])

    assets = DataAsset.objects.filter(owner=request.user).select_related('upload')
    domains = assets.values_list('domain', flat=True).distinct().exclude(domain='')
    sources = DataAsset.SOURCE_CHOICES

    return render(request, 'catalog/home.html', {
        'assets': assets[:50], 'q': q, 'domain': domain,
        'source': source, 'domains': domains, 'sources': sources,
    })


@login_required
def asset_detail(request, pk):
    asset  = get_object_or_404(DataAsset, pk=pk, owner=request.user)
    inputs  = LineageEdge.objects.filter(destination=asset.upload).select_related('source')
    outputs = LineageEdge.objects.filter(source=asset.upload).select_related('destination')
    return render(request, 'catalog/asset.html', {
        'asset': asset, 'inputs': inputs, 'outputs': outputs,
    })


@login_required
@require_POST
def update_asset(request, pk):
    asset = get_object_or_404(DataAsset, pk=pk, owner=request.user)
    asset.name        = request.POST.get('name', asset.name)[:150]
    asset.description = request.POST.get('description', '')
    asset.tags        = request.POST.get('tags', '')[:300]
    asset.domain      = request.POST.get('domain', '')[:50]
    asset.is_sensitive = 'is_sensitive' in request.POST
    asset.refresh_frequency = request.POST.get('refresh_frequency', '')
    asset.quality_score = asset.compute_quality_score()
    asset.save()
    messages.success(request, 'Catalog entry updated.')
    return redirect('catalog:asset', pk=pk)
