"""Client CardMarket (MKM API v2.0) — recherche catalogue + dépôt de stock.

CardMarket est catalogue : on ne « crée » pas d'annonce libre, on rattache la
carte à un produit du catalogue puis on dépose du stock (prix, état, langue,
foil, commentaire). Pas de photo à fournir.

Auth : OAuth 1.0a (HMAC-SHA1) signé à chaque requête, via une « dedicated app »
CardMarket. Aucune clé en dur — tout via `.env.local` :
- `MKM_ENV` = `production` | `sandbox`
- `MKM_APP_TOKEN`, `MKM_APP_SECRET`, `MKM_ACCESS_TOKEN`, `MKM_ACCESS_SECRET`
- `MKM_GAME_ID` (def. 6 = Pokémon), `MKM_LANGUAGE_ID` (def. 7 = japonais)

⚠️ Signature écrite d'après la spec MKM ; à valider en réel dès réception des
clés (les 4 jetons de l'app dédiée).
"""
import hashlib
import hmac
import time
import urllib.parse as up
import uuid
import xml.sax.saxutils as _x

import requests
from django.conf import settings

from .base import MarketplaceAPIError, require

_HOSTS = {
    "production": "https://api.cardmarket.com/ws/v2.0/output.json",
    "sandbox": "https://sandbox.cardmarket.com/ws/v2.0/output.json",
}
# États normalisés → codes d'état MKM.
_CONDITION = {"mint": "MT", "near_mint": "NM", "excellent": "EX",
              "good": "GD", "played": "PL"}


class CardmarketClient:
    def __init__(self):
        self.env = getattr(settings, "MKM_ENV", "sandbox") or "sandbox"
        self.base = _HOSTS.get(self.env, _HOSTS["sandbox"])
        self.game_id = getattr(settings, "MKM_GAME_ID", 6) or 6
        self.language_id = getattr(settings, "MKM_LANGUAGE_ID", 7) or 7

    # ── Signature OAuth 1.0a (spécificité MKM : realm = URL de la requête) ────
    def _auth_header(self, method, url):
        require("MKM_APP_TOKEN", "MKM_APP_SECRET", "MKM_ACCESS_TOKEN", "MKM_ACCESS_SECRET")
        parts = up.urlparse(url)
        base_url = f"{parts.scheme}://{parts.netloc}{parts.path}"
        query = dict(up.parse_qsl(parts.query))
        oauth = {
            "oauth_consumer_key": settings.MKM_APP_TOKEN,
            "oauth_token": settings.MKM_ACCESS_TOKEN,
            "oauth_nonce": uuid.uuid4().hex,
            "oauth_timestamp": str(int(time.time())),
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_version": "1.0",
        }
        params = {**query, **oauth}
        enc = {up.quote(k, safe=""): up.quote(str(v), safe="") for k, v in params.items()}
        param_str = "&".join(f"{k}={enc[k]}" for k in sorted(enc))
        base_string = "&".join([method.upper(), up.quote(base_url, safe=""),
                                 up.quote(param_str, safe="")])
        signing_key = f"{up.quote(settings.MKM_APP_SECRET, safe='')}&" \
                      f"{up.quote(settings.MKM_ACCESS_SECRET, safe='')}"
        sig = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
        oauth["oauth_signature"] = up.quote(
            __import__("base64").b64encode(sig).decode(), safe="")
        header = 'OAuth realm="%s", ' % base_url
        header += ", ".join(f'{k}="{v}"' for k, v in {
            "oauth_consumer_key": up.quote(oauth["oauth_consumer_key"], safe=""),
            "oauth_token": up.quote(oauth["oauth_token"], safe=""),
            "oauth_nonce": oauth["oauth_nonce"],
            "oauth_timestamp": oauth["oauth_timestamp"],
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_version": "1.0",
            "oauth_signature": oauth["oauth_signature"],
        }.items())
        return header

    def _get(self, path, params=None):
        url = self.base + path
        if params:
            url += "?" + up.urlencode(params)
        r = requests.get(url, headers={"Authorization": self._auth_header("GET", url)},
                         timeout=40)
        if r.status_code not in (200, 206):
            raise MarketplaceAPIError(f"MKM GET {path} {r.status_code}: {r.text[:300]}")
        return r.json() if r.text.strip() else {}

    def _post(self, path, xml_body):
        url = self.base + path
        r = requests.post(url, data=xml_body.encode("utf-8"),
                          headers={"Authorization": self._auth_header("POST", url),
                                   "Content-Type": "application/xml"}, timeout=40)
        if r.status_code not in (200, 201):
            raise MarketplaceAPIError(f"MKM POST {path} {r.status_code}: {r.text[:300]}")
        return r.json() if r.text.strip() else {}

    # ── Catalogue + stock ────────────────────────────────────────────────────
    def find_product(self, search):
        """Cherche un produit du catalogue (retourne la liste des correspondances)."""
        data = self._get("/products/find", {"search": search, "idGame": self.game_id,
                                            "idLanguage": self.language_id})
        return data.get("product", [])

    def add_stock(self, product_id, price, condition="near_mint", count=1,
                  is_foil=False, comments="", language_id=None):
        """Dépose un article dans le stock pour un produit du catalogue."""
        cond = _CONDITION.get(condition, "NM")
        lang = language_id or self.language_id
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
<request>
  <article>
    <idProduct>{int(product_id)}</idProduct>
    <idLanguage>{int(lang)}</idLanguage>
    <count>{int(count)}</count>
    <price>{float(price):.2f}</price>
    <condition>{cond}</condition>
    <isFoil>{"true" if is_foil else "false"}</isFoil>
    <comments>{_x.escape(comments or "")}</comments>
  </article>
</request>"""
        return self._post("/stock", body)
