from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import CATEGORIES, Blog, PressItem


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


@login_required
def articles(request):
    """List view des articles (communiqués + brouillons) avec image de référence."""
    cat = request.GET.get("cat", "")
    etat = request.GET.get("etat", "")  # brouillon / valide / publie / vide
    qs = PressItem.objects.select_related("blog_cible").all()
    if cat:
        qs = qs.filter(categorie=cat)
    if etat == "rediges":
        qs = qs.filter(draft_statut__in=["brouillon", "valide", "publie"])
    elif etat:
        qs = qs.filter(draft_statut=etat)
    items = list(qs[:200])
    cats = [(slug, label, PressItem.objects.filter(categorie=slug).count())
            for slug, label in CATEGORIES]
    return render(request, "veille/articles.html", {
        "items": items, "cats": cats, "cat": cat, "etat": etat,
        "total": qs.count(), "active_nav": "veille",
    })


@login_required
def article_detail(request, pk):
    """Fiche article : carrousel d'images + brouillon complet (plume de Thérèse)."""
    item = get_object_or_404(PressItem.objects.select_related("blog_cible"), pk=pk)
    return render(request, "veille/article_detail.html", {
        "item": item, "images": item.carrousel, "active_nav": "veille",
    })
