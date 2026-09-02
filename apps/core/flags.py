"""Feature flags minimalistes — lit ``config/feature_flags.yml`` (source de vérité du harnais).

Aucune dépendance à Django dans le cœur (testable hors-ligne) ; l'adaptateur Django est en bas du fichier.

    from apps.core.flags import is_enabled, flag_required

    FLAG = "billing_dashboard_v1"                      # déclaré dans config/feature_flags.yml (Règle 3)
    if is_enabled(FLAG, request.user): ...
    @flag_required(FLAG)                               # 404 si le flag est fermé pour cet utilisateur
    def billing_dashboard(request): ...
    {% if flags.billing_dashboard_v1 %} … {% endif %}  # dans un template, via le context processor ci-dessous

Résolution, dans l'ordre :
  1. variable d'environnement FLAG_<NOM_EN_MAJUSCULES>
     (kill switch sans PR : ``FLAG_BILLING_DASHBOARD_V1=off`` + redémarrage du service)
  2. état du registre : off → False · on / permanent → True ·
     rollout → liste blanche ``allow_users`` (usernames) puis bucket déterministe sha256(nom:user.pk) < percentage
Un flag ABSENT du registre lève KeyError : on ne code jamais derrière un flag non déclaré (Règle 3).
Chemin d'évolution : django-waffle expose la même signature ``is_enabled(name, user)``.
"""

from __future__ import annotations

import hashlib
import os
from functools import lru_cache, wraps
from pathlib import Path
from typing import Any

import yaml

_TRUTHY = {"1", "true", "on", "yes"}
_ROOT = Path(__file__).resolve().parents[2]


def registry_path() -> Path:
    return Path(os.environ.get("FEATURE_FLAGS_FILE", _ROOT / "config" / "feature_flags.yml"))


@lru_cache(maxsize=1)
def _load(path: str) -> dict[str, dict[str, Any]]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    flags: dict[str, dict[str, Any]] = {}
    for f in data.get("flags") or []:
        state = f.get("state", "off")
        state = "on" if state is True else "off" if state is False else str(state)
        flags[str(f["name"])] = {**f, "state": state}
    return flags


def registry() -> dict[str, dict[str, Any]]:
    """Registre chargé une fois par processus (``reload()`` pour forcer la relecture)."""
    return _load(str(registry_path()))


def reload() -> None:
    _load.cache_clear()


def _bucket(name: str, key: str) -> int:
    digest = hashlib.sha256(f"{name}:{key}".encode()).hexdigest()
    return int(digest[:8], 16) % 100


def is_enabled(name: str, user: Any = None) -> bool:
    flag = registry().get(name)
    if flag is None:
        raise KeyError(
            f"feature flag inconnu : {name!r} — déclare-le : scripts/ci/flags_registry.py add --name {name} …"
        )

    env = os.environ.get("FLAG_" + name.upper())
    if env is not None:
        return env.strip().lower() in _TRUTHY

    state = flag["state"]
    if state in ("on", "permanent"):
        return True
    if state == "off":
        return False
    if state == "rollout":
        if user is None or not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "username", None) in set(flag.get("allow_users") or []):
            return True
        pct = int(flag.get("percentage") or 0)
        return pct > 0 and _bucket(name, str(getattr(user, "pk", ""))) < pct
    raise ValueError(f"état de flag invalide pour {name}: {state!r}")


# ---------------------------------------------------------------------------------------------
# Adaptateur Django (importé paresseusement : le cœur reste utilisable sans Django)
# ---------------------------------------------------------------------------------------------


class FlagProxy:
    """``flags.billing_dashboard_v1`` dans un template → ``is_enabled(...)`` pour l'utilisateur courant."""

    def __init__(self, user: Any = None):
        self._user = user

    def __getitem__(self, name: str) -> bool:
        try:
            return is_enabled(name, self._user)
        except KeyError:
            # dans un template, un flag inconnu n'explose pas : il est fermé (flag-check le signale en CI)
            return False

    __getattr__ = __getitem__


def feature_flags(request: Any) -> dict[str, FlagProxy]:
    """Context processor — à ajouter dans TEMPLATES[...]["OPTIONS"]["context_processors"] :
    ``"apps.core.flags.feature_flags"``."""
    return {"flags": FlagProxy(getattr(request, "user", None))}


def flag_required(name: str):
    """Décorateur de vue : 404 si le flag est fermé pour l'utilisateur (la fonctionnalité « n'existe pas »)."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not is_enabled(name, getattr(request, "user", None)):
                from django.http import Http404  # import local : pas de Django requis hors vues

                raise Http404
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
