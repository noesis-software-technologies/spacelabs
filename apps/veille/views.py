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
@ensure_csrf_cookie
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
    # Suivi publication (2e panneau) : poussés aujourd'hui / 7 derniers jours
    today = timezone.localdate()
    pousses = list(PressItem.objects.exclude(mcp_pushed_at__isnull=True)
                   .order_by("-mcp_pushed_at")[:60])
    suivi_today = [p for p in pousses if p.mcp_pushed_at.date() == today]
    suivi_semaine = [p for p in pousses
                     if today - _dt.timedelta(days=7) <= p.mcp_pushed_at.date() < today]
    return render(request, "veille/articles.html", {
        "items": items, "cats": cats, "cat": cat, "etat": etat,
        "total": qs.count(), "active_nav": "veille",
        "suivi_today": suivi_today, "suivi_semaine": suivi_semaine,
        "suivi_pub": sum(1 for p in pousses if p.mcp_status == "published"),
        "suivi_draft": sum(1 for p in pousses if p.mcp_status == "draft"),
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
    elif action == "delete_image":
        url = str(data.get("url", ""))
        item.images_local = [u for u in (item.images_local or []) if u != url]
        item.images = [u for u in (item.images or []) if u != url]
        item.galerie = [u for u in (item.galerie or []) if u != url]
        if item.image_url == url:
            item.image_url = ""
        if item.cover_url == url:
            item.cover_url = ""
        item.save(update_fields=["images_local", "images", "galerie", "image_url", "cover_url"])
        return JsonResponse({"ok": True, "image_ref": item.image_ref, "gallery": item.carrousel})
    else:
        return JsonResponse({"ok": False, "err": "action"}, status=400)
    return JsonResponse({"ok": True, "image_ref": item.image_ref})


def _liens_constellation(it):
    """Articles liés (inter-maillage) + leur état de publication sur le blog."""
    pks = [lk.get("pk") for lk in (it.liens_internes or []) if lk.get("pk")]
    if not pks:
        return []
    par_pk = {p.pk: p for p in PressItem.objects.filter(pk__in=pks)}
    out = []
    for lk in it.liens_internes:
        cible = par_pk.get(lk.get("pk"))
        if not cible:
            continue
        out.append({
            "pk": cible.pk,
            "titre": lk.get("titre") or cible.draft_titre or cible.sujet,
            "slug": cible.slug,
            "redige": cible.draft_statut in ("brouillon", "valide", "publie"),
            "published": bool(cible.mcp_article_id),
        })
    return out


@login_required
def article_quick(request, pk):
    """Aperçu JSON pour la pop-up quick view de la liste."""
    it = get_object_or_404(PressItem, pk=pk)
    return JsonResponse({
        "pk": it.pk,
        "titre": it.draft_titre or it.sujet,
        "chapo": it.draft_chapo,
        "corps": (it.draft_corps or "")[:900],
        "cover": it.image_ref,
        "categorie": it.get_categorie_display(),
        "statut": it.draft_statut,
        "publier_le": it.publier_le.isoformat() if it.publier_le else "",
        "mcp_article_id": it.mcp_article_id,
        "images": len(it.carrousel),
        "liens": _liens_constellation(it),
    })


@login_required
@require_POST
def article_publish(request, pk):
    """Pousse l'article comme BROUILLON sur le MCP 13 Atmosphère (jamais publié).

    Renvoie aussi les articles liés (inter-maillage) encore absents du blog, pour
    suggérer de les pousser et garder la constellation cohérente (backlinks vivants).
    """
    from apps.veille import mcp
    it = get_object_or_404(PressItem, pk=pk)
    res = mcp.publish_item(it)
    if res.get("ok"):
        manquants = [lk for lk in _liens_constellation(it)
                     if lk["redige"] and not lk["published"]]
        res["lies_manquants"] = manquants
    return JsonResponse(res, status=200 if res.get("ok") else 502)


def _collect_related(item, limit=60):
    """Parcours RÉCURSIF du graphe d'inter-maillage : liés, puis liés des liés…

    Renvoie les PressItem rédigés, encore absents du blog, atteignables depuis
    `item` (constellation connectée). Anti-cycle via l'ensemble `seen`.
    """
    from collections import deque
    seen = {item.pk}
    queue = deque(lk.get("pk") for lk in (item.liens_internes or []) if lk.get("pk"))
    out = []
    while queue and len(out) < limit:
        cpk = queue.popleft()
        if cpk in seen:
            continue
        seen.add(cpk)
        cible = PressItem.objects.filter(pk=cpk).first()
        if not cible:
            continue
        if cible.draft_statut in ("brouillon", "valide", "publie") and not cible.mcp_article_id:
            out.append(cible)
        for lk in (cible.liens_internes or []):
            if lk.get("pk") and lk["pk"] not in seen:
                queue.append(lk["pk"])
    return out


@login_required
@require_POST
def article_publish_related(request, pk):
    """Pousse en BROUILLON, en cascade récursive, toute la constellation connectée
    (liés + liés des liés) encore absente du blog. 13-atmosphere reste publicateur."""
    from apps.veille import mcp
    it = get_object_or_404(PressItem, pk=pk)
    resultats = []
    for cible in _collect_related(it):
        r = mcp.publish_item(cible)
        resultats.append({"pk": cible.pk, "titre": (cible.draft_titre or cible.sujet)[:80],
                          "ok": r.get("ok"), "article_id": r.get("article_id"),
                          "error": r.get("error")})
        if not r.get("ok"):
            break  # MCP tombé : on arrête proprement
    ok = sum(1 for r in resultats if r["ok"])
    return JsonResponse({"ok": True, "pousses": ok, "total": len(resultats), "resultats": resultats})


@login_required
@require_POST
def mcp_status_refresh(request):
    """Rafraîchit l'état de publication (brouillon/publié) via list_drafts du MCP."""
    from apps.veille import mcp
    return JsonResponse(mcp.refresh_statuses())
