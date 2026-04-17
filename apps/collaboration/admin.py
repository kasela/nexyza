from django.contrib import admin
from .models import CollabSession, CollabComment, CollabAction
admin.site.register(CollabSession)
admin.site.register(CollabComment)
admin.site.register(CollabAction)
