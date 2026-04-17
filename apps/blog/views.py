from django.shortcuts import render, get_object_or_404
from .models import BlogPost


def blog_index(request):
    featured = BlogPost.objects.filter(is_published=True, is_featured=True)[:3]
    posts    = BlogPost.objects.filter(is_published=True)
    category = request.GET.get('cat', '')
    if category:
        posts = posts.filter(category=category)
    return render(request, 'blog/index.html', {
        'posts':    posts[:20],
        'featured': featured,
        'category': category,
        'categories': BlogPost.CATEGORY_CHOICES,
    })


def blog_post(request, slug):
    post    = get_object_or_404(BlogPost, slug=slug, is_published=True)
    related = BlogPost.objects.filter(
        is_published=True, category=post.category
    ).exclude(pk=post.pk)[:3]
    return render(request, 'blog/post.html', {'post': post, 'related': related})
