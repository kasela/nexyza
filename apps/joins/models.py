import uuid
from django.db import models
from django.conf import settings


class JoinConfig(models.Model):
    JOIN_INNER = 'inner'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    JOIN_LEFT  = 'left'
    JOIN_RIGHT = 'right'
    JOIN_OUTER = 'outer'
    JOIN_CHOICES = [
        (JOIN_INNER, 'Inner Join'),
        (JOIN_LEFT,  'Left Join'),
        (JOIN_RIGHT, 'Right Join'),
        (JOIN_OUTER, 'Outer Join'),
    ]

    user         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='joins')
    name         = models.CharField(max_length=100, default='Joined Dataset')
    left_upload  = models.ForeignKey('analyser.FileUpload', on_delete=models.CASCADE, related_name='joins_as_left')
    right_upload = models.ForeignKey('analyser.FileUpload', on_delete=models.CASCADE, related_name='joins_as_right')
    left_key     = models.CharField(max_length=255)
    right_key    = models.CharField(max_length=255)
    join_type    = models.CharField(max_length=10, choices=JOIN_CHOICES, default=JOIN_INNER)
    result_upload = models.ForeignKey('analyser.FileUpload', on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='created_by_join')
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.left_upload.original_name} ⋈ {self.right_upload.original_name})"
