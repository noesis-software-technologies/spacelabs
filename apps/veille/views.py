from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

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
    # Pré-rédaction : compteurs de brouillons + calendrier à venir
    draft_stats = dict(PressItem.objects.values_list("draft_statut")
                       .annotate(n=Count("id")).values_list("draft_statut", "n"))
    calendrier = list(
        PressItem.objects.filter(publier_le__isnull=False,
                                 publier_le__gte=timezone.localdate())
        .order_by("publier_le")[:20]
    )
    return render(request, "veille/dashboard.html", {
        "blogs": blogs, "non_assignes": non_assignes, "stats": stats,
        "draft_stats": draft_stats, "calendrier": calendrier,
        "active_nav": "veille",
    })
