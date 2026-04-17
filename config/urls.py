from config.views import handler_404, handler_500

handler404 = handler_404
handler500 = handler_500

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('billing/', include('apps.billing.urls', namespace='billing')),
    path('connectors/', include('apps.connectors.urls', namespace='connectors')),
    path('dashboard/', include('apps.dashboard.urls', namespace='dashboard')),
    path('workspace/', include('apps.analyser.urls', namespace='analyser')),
    path('', include('apps.core.urls', namespace='core')),
    path('blog/', include('apps.blog.urls', namespace='blog')),
    path('api/v1/', include('apps.api.urls', namespace='api')),
    path('teams/', include('apps.teams.urls', namespace='teams')),
    path('nlq/', include('apps.nlq.urls', namespace='nlq')),
    path('pipeline/', include('apps.pipeline.urls', namespace='pipeline')),
    path('embed/', include('apps.embed.urls', namespace='embed')),
    path('settings/branding/', include('apps.whitelabel.urls', namespace='whitelabel')),
    path('audit/', include('apps.audit.urls', namespace='audit')),
    path('join/', include('apps.joins.urls', namespace='joins')),
    path('formula/', include('apps.formulas.urls', namespace='formulas')),
    path('anomaly/', include('apps.anomaly.urls', namespace='anomaly')),
    path('version/', include('apps.versioning.urls', namespace='versioning')),
    path('export/', include('apps.exports.urls', namespace='exports')),
    path('notify/', include('apps.notifications.urls', namespace='notifications')),
    path('search/', include('apps.search.urls', namespace='search')),
    path('widgets/', include('apps.widgets.urls', namespace='widgets')),
    path('forecast/', include('apps.forecasting.urls', namespace='forecasting')),
    path('reports/builder/', include('apps.reportbuilder.urls', namespace='reportbuilder')),
    path('webhooks/', include('apps.webhooks.urls', namespace='webhooks')),
    path('roles/', include('apps.roles.urls', namespace='roles')),
    path('catalog/', include('apps.catalog.urls', namespace='catalog')),
    path('collab/', include('apps.collaboration.urls', namespace='collaboration')),
    path('reports/', include('apps.reports.urls', namespace='reports')),
    path('clean/', include('apps.cleaner.urls', namespace='cleaner')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
