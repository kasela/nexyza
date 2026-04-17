import uuid
from django.db import models
from django.utils.text import slugify
from django.conf import settings


class BlogPost(models.Model):
    CATEGORY_CHOICES = [
        ('tutorial',    'Tutorial'),
        ('product',     'Product Update'),
        ('analytics',   'Data & Analytics'),
        ('tips',        'Tips & Tricks'),
        ('case-study',  'Case Study'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title          = models.CharField(max_length=200)
    slug           = models.SlugField(unique=True, blank=True, max_length=220)
    summary        = models.TextField(max_length=400, help_text='Shown in listing + meta description')
    content        = models.TextField(help_text='Markdown or HTML')
    category       = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='analytics')
    cover_image    = models.URLField(blank=True, help_text='Absolute URL to cover image')
    og_image       = models.URLField(blank=True, help_text='Override OG image (defaults to cover_image)')
    author_name    = models.CharField(max_length=80, default='Nexyza Team')
    author_avatar  = models.URLField(blank=True)
    reading_time   = models.PositiveSmallIntegerField(default=5, help_text='Minutes')
    is_published   = models.BooleanField(default=False)
    is_featured    = models.BooleanField(default=False)
    published_at   = models.DateTimeField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-created_at']
        verbose_name      = 'Blog Post'
        verbose_name_plural = 'Blog Posts'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)
            slug, n = base, 1
            while BlogPost.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f'{base}-{n}', n + 1
            self.slug = slug
        if self.is_published and not self.published_at:
            from django.utils import timezone
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_og_image(self):
        return self.og_image or self.cover_image or 'https://nexyza.com/static/img/og-default.png'
