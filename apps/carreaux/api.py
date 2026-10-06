"""API interne Carreaux — gestion inventaire cross-plateforme.

Authentification : Bearer token (CARREAUX_API_TOKEN dans .env.local).

Endpoints :
  GET  /carreaux/api/inventory/            → état de tout l'inventaire
  GET  /carreaux/api/inventory/<id>/       → état d'un produit
  POST /carreaux/api/sold/<stock_item_id>/ → marquer vendu partout
  POST /carreaux/api/activate/<product_id>/ → (ré)activer un produit boutique
  POST /carreaux/api/deactivate/<product_id>/ → désactiver un produit boutique
  GET  /carreaux/api/orders/               → commandes boutique récentes
"""
import functools

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.vinted.models import StockItem

from .models import BoutiqueOrder, BoutiqueProduct


def _require_token(fn):
    @functools.wraps(fn)
    def wrapper(request, *args, **kwargs):
        token = request.META.get("HTTP_AUTHORIZATION", "")
        if token.startswith("Bearer "):
            token = token[7:]
        expected = getattr(settings, "CARREAUX_API_TOKEN", "")
        if not expected or token != expected:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        return fn(request, *args, **kwargs)
    return wrapper


@csrf_exempt
@require_http_methods(["GET"])
@_require_token
def inventory(request):
    products = BoutiqueProduct.objects.select_related("stock_item").all()
    return JsonResponse({
        "count": products.count(),
        "products": [
            {
                "id": p.pk,
                "slug": p.slug,
                "titre": p.titre,
                "prix_vente": str(p.prix_vente),
                "actif": p.actif,
                "stock_item_id": p.stock_item_id,
                "stock_statut": p.stock_item.statut if p.stock_item else None,
            }
            for p in products
        ],
    })


@csrf_exempt
@require_http_methods(["GET"])
@_require_token
def inventory_detail(request, product_id):
    try:
        p = BoutiqueProduct.objects.select_related("stock_item").get(pk=product_id)
    except BoutiqueProduct.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)
    return JsonResponse({
        "id": p.pk, "slug": p.slug, "titre": p.titre,
        "prix_vente": str(p.prix_vente), "actif": p.actif,
        "stock_item_id": p.stock_item_id,
        "stock_statut": p.stock_item.statut if p.stock_item else None,
    })


@csrf_exempt
@require_http_methods(["POST"])
@_require_token
def mark_sold(request, stock_item_id):
    """Marque un StockItem comme vendu — déclenche le signal cross-plateforme."""
    try:
        item = StockItem.objects.get(pk=stock_item_id)
    except StockItem.DoesNotExist:
        return JsonResponse({"error": "StockItem not found"}, status=404)
    if item.statut == "vendu":
        return JsonResponse({"ok": True, "status": "already_sold"})
    item.statut = "vendu"
    item.save(update_fields=["statut"])
    return JsonResponse({"ok": True, "stock_item_id": stock_item_id, "statut": "vendu"})


@csrf_exempt
@require_http_methods(["POST"])
@_require_token
def activate_product(request, product_id):
    try:
        p = BoutiqueProduct.objects.get(pk=product_id)
    except BoutiqueProduct.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)
    p.actif = True
    p.save(update_fields=["actif", "maj_le"])
    return JsonResponse({"ok": True, "product_id": product_id, "actif": True})


@csrf_exempt
@require_http_methods(["POST"])
@_require_token
def deactivate_product(request, product_id):
    try:
        p = BoutiqueProduct.objects.get(pk=product_id)
    except BoutiqueProduct.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)
    p.actif = False
    p.save(update_fields=["actif", "maj_le"])
    return JsonResponse({"ok": True, "product_id": product_id, "actif": False})


@csrf_exempt
@require_http_methods(["GET"])
@_require_token
def orders(request):
    limit = min(int(request.GET.get("limit", 20)), 100)
    qs = BoutiqueOrder.objects.order_by("-cree_le")[:limit]
    return JsonResponse({
        "orders": [
            {
                "id": o.pk, "ref": o.ref, "email": o.email,
                "total": str(o.total), "statut": o.statut,
                "cree_le": o.cree_le.isoformat(),
            }
            for o in qs
        ]
    })
