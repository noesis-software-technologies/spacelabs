"""Client eBay — vente directe (prix fixe) et enchères.

Deux familles d'API eBay, choisies selon le type de mise en vente :
- **Prix fixe** → Sell API (REST) : Inventory Item → Offer → Publish.
- **Enchères** → Trading API (XML, `AddItem`, ListingType=Chinese) : la Sell
  API ne gère pas les enchères, on passe par l'API historique.

Authentification (aucun secret en dur — tout via `.env.local`) :
- `EBAY_ENV` = `sandbox` | `production`
- `EBAY_OAUTH_TOKEN` : jeton d'accès utilisateur (le plus simple), OU
- `EBAY_REFRESH_TOKEN` + `EBAY_CLIENT_ID` + `EBAY_CLIENT_SECRET` : on frappe
  le jeton d'accès à la volée (grant_type=refresh_token).
- `EBAY_MARKETPLACE` (def. `EBAY_FR`), `EBAY_MERCHANT_LOCATION_KEY`,
  `EBAY_FULFILLMENT_POLICY_ID`, `EBAY_PAYMENT_POLICY_ID`, `EBAY_RETURN_POLICY_ID`
  (requis par la Sell API pour publier une offre).

⚠️ Le flux est écrit d'après la spec eBay ; à valider en réel dès réception des
clés (comptes développeur + policies configurées côté eBay).
"""
import base64
import time
import xml.sax.saxutils as _x

import requests
from django.conf import settings

from .base import MarketplaceAPIError, MarketplaceConfigError, require

_HOSTS = {
    "production": {"api": "https://api.ebay.com", "trading": "https://api.ebay.com/ws/api.dll"},
    "sandbox": {"api": "https://api.sandbox.ebay.com",
                "trading": "https://api.sandbox.ebay.com/ws/api.dll"},
}
# États normalisés → conditionId eBay (2750 = « Graded » pour les cartes gradées).
_CONDITION = {"mint": "2750", "near_mint": "2750", "excellent": "2750",
              "good": "3000", "played": "3000"}
_SITEID = {"EBAY_FR": "71", "EBAY_US": "0", "EBAY_GB": "3", "EBAY_DE": "77"}


class EbayClient:
    def __init__(self):
        self.env = getattr(settings, "EBAY_ENV", "sandbox") or "sandbox"
        self.hosts = _HOSTS.get(self.env, _HOSTS["sandbox"])
        self.marketplace = getattr(settings, "EBAY_MARKETPLACE", "EBAY_FR") or "EBAY_FR"
        self._token = None

    # ── Auth ────────────────────────────────────────────────────────────────
    def access_token(self):
        if self._token:
            return self._token
        direct = getattr(settings, "EBAY_OAUTH_TOKEN", "")
        if direct:
            self._token = direct
            return direct
        require("EBAY_REFRESH_TOKEN", "EBAY_CLIENT_ID", "EBAY_CLIENT_SECRET")
        creds = f"{settings.EBAY_CLIENT_ID}:{settings.EBAY_CLIENT_SECRET}".encode()
        basic = base64.b64encode(creds).decode()
        r = requests.post(
            f"{self.hosts['api']}/identity/v1/oauth2/token",
            headers={"Authorization": f"Basic {basic}",
                     "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "refresh_token",
                  "refresh_token": settings.EBAY_REFRESH_TOKEN,
                  "scope": "https://api.ebay.com/oauth/api_scope/sell.inventory"},
            timeout=30)
        if r.status_code != 200:
            raise MarketplaceAPIError(f"OAuth eBay {r.status_code}: {r.text[:300]}")
        self._token = r.json()["access_token"]
        return self._token

    def _rest_headers(self):
        return {"Authorization": f"Bearer {self.access_token()}",
                "Content-Type": "application/json",
                "Content-Language": "fr-FR",
                "X-EBAY-C-MARKETPLACE-ID": self.marketplace}

    # ── Prix fixe (Sell / Inventory API) ─────────────────────────────────────
    def publish_fixed(self, listing):
        require("EBAY_MERCHANT_LOCATION_KEY", "EBAY_FULFILLMENT_POLICY_ID",
                "EBAY_PAYMENT_POLICY_ID", "EBAY_RETURN_POLICY_ID")
        api = self.hosts["api"]
        sku = listing.external_id or f"card-{listing.pk}"
        images = listing.resolved_images()
        # 1) Inventory item
        item = {
            "availability": {"shipToLocationAvailability": {"quantity": listing.quantite or 1}},
            "condition": _CONDITION.get(listing.etat, "2750"),
            "product": {
                "title": listing.resolved_title()[:80],
                "description": listing.resolved_description() or listing.resolved_title(),
                "imageUrls": images[:12],
            },
        }
        r = requests.put(f"{api}/sell/inventory/v1/inventory_item/{sku}",
                         headers=self._rest_headers(), json=item, timeout=40)
        if r.status_code not in (200, 201, 204):
            raise MarketplaceAPIError(f"inventory_item {r.status_code}: {r.text[:300]}")
        # 2) Offer
        offer = {
            "sku": sku, "marketplaceId": self.marketplace, "format": "FIXED_PRICE",
            "availableQuantity": listing.quantite or 1,
            "categoryId": getattr(settings, "EBAY_CATEGORY_ID", "") or None,
            "listingDescription": item["product"]["description"],
            "pricingSummary": {"price": {"value": str(listing.prix), "currency": "EUR"}},
            "listingPolicies": {
                "fulfillmentPolicyId": settings.EBAY_FULFILLMENT_POLICY_ID,
                "paymentPolicyId": settings.EBAY_PAYMENT_POLICY_ID,
                "returnPolicyId": settings.EBAY_RETURN_POLICY_ID,
            },
            "merchantLocationKey": settings.EBAY_MERCHANT_LOCATION_KEY,
        }
        r = requests.post(f"{api}/sell/inventory/v1/offer",
                          headers=self._rest_headers(), json=offer, timeout=40)
        if r.status_code not in (200, 201):
            raise MarketplaceAPIError(f"offer {r.status_code}: {r.text[:300]}")
        offer_id = r.json().get("offerId")
        # 3) Publish
        r = requests.post(f"{api}/sell/inventory/v1/offer/{offer_id}/publish",
                          headers=self._rest_headers(), timeout=40)
        if r.status_code not in (200, 201):
            raise MarketplaceAPIError(f"publish {r.status_code}: {r.text[:300]}")
        listing_id = r.json().get("listingId", "")
        base = "https://www.ebay.fr/itm/" if self.env == "production" else "https://sandbox.ebay.com/itm/"
        return {"external_id": offer_id, "listing_id": listing_id,
                "url": (base + listing_id) if listing_id else ""}

    # ── Enchères (Trading API AddItem) ───────────────────────────────────────
    def publish_auction(self, listing):
        require("EBAY_TRADING_TOKEN")
        site = _SITEID.get(self.marketplace, "71")
        cat = getattr(settings, "EBAY_CATEGORY_ID", "") or "183454"  # cartes à collectionner
        days = listing.duree_jours or 7
        pics = "".join(f"<PictureURL>{_x.escape(u)}</PictureURL>"
                       for u in listing.resolved_images()[:12])
        reserve = (f"<ReservePrice currencyID='EUR'>{listing.prix_reserve}</ReservePrice>"
                   if listing.prix_reserve else "")
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<AddItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <RequesterCredentials><eBayAuthToken>{_x.escape(settings.EBAY_TRADING_TOKEN)}</eBayAuthToken></RequesterCredentials>
  <Item>
    <Title>{_x.escape(listing.resolved_title()[:80])}</Title>
    <Description><![CDATA[{listing.resolved_description() or listing.resolved_title()}]]></Description>
    <PrimaryCategory><CategoryID>{cat}</CategoryID></PrimaryCategory>
    <ListingType>Chinese</ListingType>
    <ListingDuration>Days_{days}</ListingDuration>
    <StartPrice currencyID="EUR">{listing.prix}</StartPrice>
    {reserve}
    <Quantity>1</Quantity>
    <Currency>EUR</Currency>
    <Country>FR</Country>
    <Location>France</Location>
    <ConditionID>{_CONDITION.get(listing.etat, "2750")}</ConditionID>
    <PictureDetails>{pics}</PictureDetails>
    <DispatchTimeMax>3</DispatchTimeMax>
  </Item>
</AddItemRequest>"""
        headers = {
            "X-EBAY-API-SITEID": site,
            "X-EBAY-API-COMPATIBILITY-LEVEL": "1193",
            "X-EBAY-API-CALL-NAME": "AddItem",
            "Content-Type": "text/xml",
        }
        r = requests.post(self.hosts["trading"], data=xml.encode("utf-8"),
                          headers=headers, timeout=60)
        if r.status_code != 200 or "<Ack>Failure</Ack>" in r.text:
            raise MarketplaceAPIError(f"AddItem: {r.text[:400]}")
        # ItemID entre <ItemID>...</ItemID>
        import re
        m = re.search(r"<ItemID>(\d+)</ItemID>", r.text)
        item_id = m.group(1) if m else ""
        base = "https://www.ebay.fr/itm/" if self.env == "production" else "https://sandbox.ebay.com/itm/"
        return {"external_id": item_id, "listing_id": item_id,
                "url": (base + item_id) if item_id else ""}
