"""Boutique Carreaux — vues e-commerce avec Stripe Checkout."""
import json
from decimal import Decimal

import stripe
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import BoutiqueOrder, BoutiqueOrderLine, BoutiqueProduct, BoutiqueReview

stripe.api_key = settings.STRIPE_SECRET_KEY

LIVRAISON = settings.BOUTIQUE_LIVRAISON
REMISE_SEUIL = settings.BOUTIQUE_REMISE_SEUIL
REMISE_PCT = settings.BOUTIQUE_REMISE_PCT


# ── Helpers panier (session) ──────────────────────────────────────────────────

def _get_cart(request):
    return request.session.get("cart", {})


def _save_cart(request, cart):
    request.session["cart"] = cart
    request.session.modified = True


def _cart_count(cart):
    return sum(cart.values())


def _cart_totals(cart):
    """Retourne (items_list, sous_total, remise, livraison, total)."""
    items = []
    sous_total = Decimal("0")
    for pid, qty in cart.items():
        try:
            p = BoutiqueProduct.objects.get(pk=int(pid), actif=True)
        except BoutiqueProduct.DoesNotExist:
            continue
        line_total = p.prix_vente * qty
        sous_total += line_total
        items.append({"product": p, "qty": qty, "sous_total": line_total})
    remise = round(sous_total * REMISE_PCT, 2) if sous_total >= REMISE_SEUIL else Decimal("0")
    total = sous_total - remise + LIVRAISON
    return items, sous_total, remise, LIVRAISON, total


# ── Vues publiques ─────────────────────────────────────────────────────────────

def catalogue(request):
    products = BoutiqueProduct.objects.filter(actif=True).select_related("stock_item")
    reviews = BoutiqueReview.objects.filter(note=5).order_by("-date")[:12]
    cart = _get_cart(request)
    return render(request, "carreaux/catalogue.html", {
        "products": products,
        "reviews": reviews,
        "cart_count": _cart_count(cart),
        "vinted_profile_url": "https://www.vinted.fr/member/ddorff/feedback",
    })


def produit(request, slug):
    product = get_object_or_404(BoutiqueProduct, slug=slug, actif=True)
    cart = _get_cart(request)
    return render(request, "carreaux/produit.html", {
        "product": product,
        "cart_count": _cart_count(cart),
    })


def panier(request):
    cart = _get_cart(request)
    items, sous_total, remise, livraison, total = _cart_totals(cart)
    return render(request, "carreaux/panier.html", {
        "items": items,
        "sous_total": sous_total,
        "remise": remise,
        "livraison": livraison,
        "total": total,
        "cart_count": _cart_count(cart),
        "remise_seuil": REMISE_SEUIL,
    })


# ── Actions panier (AJAX) ──────────────────────────────────────────────────────

@require_POST
def panier_add(request, product_id):
    product = get_object_or_404(BoutiqueProduct, pk=product_id, actif=True)
    cart = _get_cart(request)
    pid = str(product_id)
    cart[pid] = cart.get(pid, 0) + 1
    _save_cart(request, cart)
    return JsonResponse({"ok": True, "cart_count": _cart_count(cart), "titre": product.titre})


@require_POST
def panier_remove(request, product_id):
    cart = _get_cart(request)
    pid = str(product_id)
    cart.pop(pid, None)
    _save_cart(request, cart)
    return JsonResponse({"ok": True, "cart_count": _cart_count(cart)})


@require_POST
def panier_vider(request):
    _save_cart(request, {})
    return JsonResponse({"ok": True, "cart_count": 0})


# ── Checkout Stripe ────────────────────────────────────────────────────────────

@require_POST
def checkout(request):
    """Créer une Stripe Checkout Session depuis le panier courant."""
    cart = _get_cart(request)
    if not cart:
        return redirect("carreaux:catalogue")

    items, sous_total, remise, livraison, total = _cart_totals(cart)
    if not items:
        return redirect("carreaux:catalogue")

    base_url = request.build_absolute_uri("/")
    line_items = []
    for item in items:
        p = item["product"]
        line_items.append({
            "price_data": {
                "currency": "eur",
                "product_data": {
                    "name": p.titre,
                    "images": [p.image_url] if p.image_url and p.image_url.startswith("http") else [],
                },
                "unit_amount": int(p.prix_vente * 100),
            },
            "quantity": item["qty"],
        })

    # Remise → coupon Stripe
    discounts = []
    if remise > 0:
        coupon = stripe.Coupon.create(
            amount_off=int(remise * 100),
            currency="eur",
            duration="once",
            name="Remise fidélité −10%",
        )
        discounts = [{"coupon": coupon.id}]

    # Frais de livraison en ligne item séparée
    line_items.append({
        "price_data": {
            "currency": "eur",
            "product_data": {"name": "Livraison"},
            "unit_amount": int(LIVRAISON * 100),
        },
        "quantity": 1,
    })

    # Créer la commande en pending avant redirect
    order = BoutiqueOrder.objects.create(
        email="",
        nom="",
        adresse="",
        sous_total=sous_total,
        remise=remise,
        livraison=LIVRAISON,
        total=total,
        statut="pending",
    )
    for item in items:
        BoutiqueOrderLine.objects.create(
            order=order,
            product=item["product"],
            prix_unitaire=item["product"].prix_vente,
            quantite=item["qty"],
        )

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=line_items,
        discounts=discounts,
        mode="payment",
        success_url=base_url + f"carreaux/success/?ref={order.ref}&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=base_url + "carreaux/cancel/",
        metadata={"order_ref": order.ref},
        billing_address_collection="required",
        shipping_address_collection={"allowed_countries": ["FR", "BE", "CH", "LU"]},
        phone_number_collection={"enabled": False},
    )

    order.stripe_session_id = session.id
    order.save(update_fields=["stripe_session_id", "maj_le"])

    return redirect(session.url, permanent=False)


@require_POST
def checkout_instant(request, product_id):
    """Achat immédiat d'un seul produit — bypass panier."""
    product = get_object_or_404(BoutiqueProduct, pk=product_id, actif=True)
    _save_cart(request, {str(product_id): 1})
    return checkout(request)


def success(request):
    ref = request.GET.get("ref", "")
    order = None
    if ref:
        try:
            order = BoutiqueOrder.objects.get(ref=ref)
        except BoutiqueOrder.DoesNotExist:
            pass
    _save_cart(request, {})
    return render(request, "carreaux/success.html", {
        "order": order,
        "cart_count": 0,
    })


def cancel(request):
    return render(request, "carreaux/cancel.html", {"cart_count": _cart_count(_get_cart(request))})


# ── Webhook Stripe ──────────────────────────────────────────────────────────────

@csrf_exempt
def webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        ref = session.get("metadata", {}).get("order_ref", "")
        try:
            order = BoutiqueOrder.objects.get(ref=ref)
        except BoutiqueOrder.DoesNotExist:
            return HttpResponse(status=200)

        order.statut = "paid"
        order.email = session.get("customer_details", {}).get("email", "") or ""
        order.nom = session.get("customer_details", {}).get("name", "") or ""
        addr = session.get("shipping_details", {}).get("address", {}) or {}
        order.adresse = "\n".join(filter(None, [
            addr.get("line1", ""), addr.get("line2", ""),
            addr.get("postal_code", ""), addr.get("city", ""), addr.get("country", ""),
        ]))
        order.save(update_fields=["statut", "email", "nom", "adresse", "maj_le"])

        # Marquer les StockItems comme vendus
        for ligne in order.lignes.select_related("product__stock_item").all():
            si = ligne.product.stock_item
            if si:
                si.statut = "vendu"
                si.save(update_fields=["statut"])
                # Signal dans carreaux/signals.py désactivera BoutiqueProduct + VintedListing

    return HttpResponse(status=200)
