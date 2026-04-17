from django.urls import re_path
from .consumers import AnalysisConsumer

websocket_urlpatterns = [
    re_path(r'ws/analysis/(?P<upload_id>[0-9a-f-]{36})/$', AnalysisConsumer.as_asgi()),
]
