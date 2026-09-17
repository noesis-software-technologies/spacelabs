from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render

from .models import Blog, PressItem


@login_required
def dashboard(request):
    blogs = list(Blog.objects.all())
    for b in blogs:
        b.items_list = list(b.items.all()[:50])
    non_assignes = PressItem.objects.filter(blog_cible__isnull=True)[:50]
    stats = {
        "total": PressItem.objects.count(),
        "par_statut": dict(PressItem.objects.values_list("statut")
                           .annotate(n=Count("id")).values_list("statut", "n")),
    }
    return render(request, "veille/dashboard.html", {
        "blogs": blogs, "non_assignes": non_assignes, "stats": stats,
        "active_nav": "veille",
    })
