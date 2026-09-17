import datetime as _dt
import json

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

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


def _liens_status(item):
    """Pour chaque lien interne : le slug cible existe-t-il (correspondance blog) ?"""
    out = []
    for lk in (item.liens_internes or []):
        cible = PressItem.objects.filter(pk=lk.get("pk")).first()
        slug = (cible.slug if cible else "") or lk.get("slug") or ""
        out.append({"pk": lk.get("pk"), "titre": lk.get("titre", ""),
                    "slug": slug, "ok": bool(slug)})
    return out


@login_required
@ensure_csrf_cookie
def article_edit(request, pk):
    """Panneau de revue avant publication : cover, ordre galerie, date, slugs."""
    item = get_object_or_404(PressItem.objects.select_related("blog_cible"), pk=pk)
    return render(request, "veille/article_edit.html", {
        "item": item,
        "galerie": item.carrousel,
        "cover": item.image_ref,
        "liens": _liens_status(item),
        "active_nav": "veille",
    })


@login_required
@require_POST
def article_save(request, pk):
    """Sauvegarde asynchrone du panneau de revue (JSON)."""
    item = get_object_or_404(PressItem, pk=pk)
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "err": "json"}, status=400)
    action = data.get("action")
    if action == "cover":
        item.cover_url = str(data.get("url", ""))[:1000]
        item.save(update_fields=["cover_url"])
    elif action == "reorder":
        order = [str(u) for u in (data.get("order") or []) if u]
        item.galerie = order
        item.save(update_fields=["galerie"])
    elif action == "pubdate":
        val = (data.get("date") or "").strip()
        try:
            item.publier_le = _dt.date.fromisoformat(val) if val else None
        except ValueError:
            return JsonResponse({"ok": False, "err": "date"}, status=400)
        item.save(update_fields=["publier_le"])
    elif action == "statut":
        st = data.get("statut")
        if st in dict(PressItem.DRAFT_STATUT):
            item.draft_statut = st
            item.save(update_fields=["draft_statut"])
    else:
        return JsonResponse({"ok": False, "err": "action"}, status=400)
    return JsonResponse({"ok": True, "image_ref": item.image_ref})
