"""Calcul de prix — arithmétique Decimal pure, sans persistance."""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

PALIERS = [
    {"label": "Palier 30 %", "taux_marque": Decimal("0.30")},
    {"label": "Palier 40 %", "taux_marque": Decimal("0.40")},
    {"label": "Palier 50 %", "taux_marque": Decimal("0.50")},
]

_CENT = Decimal("0.01")


def _arrondi(v: Decimal) -> Decimal:
    return v.quantize(_CENT, rounding=ROUND_HALF_UP)


def parse_decimal(raw: str) -> Decimal | None:
    try:
        v = Decimal(raw.replace(",", "."))
        if v < 0:
            return None
        return v
    except (InvalidOperation, AttributeError):
        return None


def calculer_tiers(pa: Decimal, frais: Decimal) -> list[dict]:
    """Retourne les 3 paliers de prix pour un coût donné.

    Formule (taux de marque sur PV) :
        C = PA + frais
        PV = C / (1 - taux_marque)
        M  = PV - C
        taux_marge_sur_cout = M / C
    """
    if pa < 0 or frais < 0:
        raise ValueError("PA et frais doivent être >= 0")

    cout = pa + frais
    result = []

    for p in PALIERS:
        tm = p["taux_marque"]
        diviseur = Decimal("1") - tm
        if diviseur <= 0:
            pv = marge = taux_marge_cout = None
            erreur = "Diviseur nul — taux de marque >= 100 %"
        elif cout == 0:
            pv = marge = taux_marge_cout = Decimal("0.00")
            erreur = None
        else:
            pv = _arrondi(cout / diviseur)
            marge = _arrondi(pv - cout)
            taux_marge_cout = _arrondi((marge / cout) * 100) if cout > 0 else None
            erreur = None

        result.append({
            "label": p["label"],
            "taux_marque_pct": int(tm * 100),
            "pv": pv,
            "marge": marge,
            "taux_marge_cout_pct": taux_marge_cout,
            "erreur": erreur,
        })

    return result
