"""Presets d'agents : des panes pré-configurés (binaire + libellé + couleur).

Un preset est une commodité, pas une dérogation. Un preset pty déclenche la
création via le pipeline `pane_create` habituel — son binaire est donc validé
comme n'importe quel `cmd` (`resolve_allowed_binary`, durcissement Sprint 17).
Un preset dont le binaire n'est pas lançable est présenté **désactivé**, jamais
caché : on montre ce qui est possible et ce qu'il reste à autoriser/installer.

Les presets par défaut ci-dessous sont un point de départ. L'exploitant peut les
remplacer par les siens via le réglage ``COCKPIT_AGENT_PRESETS`` (liste d'objets,
en settings ou en JSON d'environnement). Quand ce réglage est fourni, il
**remplace** la liste par défaut : on garde un contrôle total et prévisible.
"""
from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True)
class AgentPreset:
    key: str
    label: str
    kind: str          # "pty" | "headless"
    color: str         # alias de token, ex. "var(--claude)"
    icon: str          # clé d'icône (cf _agent_picker.html)
    cmd: str = ""      # binaire + arguments (pty uniquement)
    description: str = ""


DEFAULT_AGENT_PRESETS = [
    AgentPreset("claude", "Claude Code", "pty", "var(--claude)", "terminal",
                cmd="claude", description="Agent de code Claude, dans un terminal"),
    AgentPreset("codex", "Codex", "pty", "var(--cyan)", "terminal",
                cmd="codex", description="Agent Codex en ligne de commande"),
    AgentPreset("cursor", "Cursor", "pty", "var(--gold)", "terminal",
                cmd="cursor-agent", description="Agent Cursor en ligne de commande"),
    AgentPreset("shell", "Terminal", "pty", "var(--text-2)", "terminal",
                cmd="bash", description="Shell générique, sans agent"),
    AgentPreset("chat", "Chat Claude", "headless", "var(--claude)", "message",
                description="Conversation Claude, sans terminal"),
]

_ALLOWED_KINDS = {"pty", "headless"}


def _preset_from_config(entry):
    """Normalise une entrée de config en AgentPreset, ou None si invalide.

    Requis : ``key`` et ``label`` non vides, ``kind`` dans {pty, headless}, et un
    ``cmd`` non vide pour un preset pty. Les champs de présentation (color, icon,
    description) ont des défauts. Une entrée invalide est ignorée — et signalée par
    ``manage.py check`` (runtime.W002), pour ne pas la découvrir en silence.
    """
    if not isinstance(entry, dict):
        return None
    key = str(entry.get("key", "")).strip()
    label = str(entry.get("label", "")).strip()
    kind = str(entry.get("kind", "pty")).strip() or "pty"
    cmd = str(entry.get("cmd", "")).strip()
    if not key or not label or kind not in _ALLOWED_KINDS:
        return None
    if kind == "pty" and not cmd:
        return None
    return AgentPreset(
        key=key, label=label, kind=kind,
        color=str(entry.get("color", "")).strip() or "var(--text-2)",
        icon=str(entry.get("icon", "")).strip() or "terminal",
        cmd=cmd,
        description=str(entry.get("description", "")).strip(),
    )


def get_agent_presets():
    """La liste effective des presets : celle configurée si fournie, sinon défauts.

    ``COCKPIT_AGENT_PRESETS`` remplace les défauts. On ne garde que les entrées
    valides ; si la config ne produit aucune entrée exploitable, on retombe sur les
    défauts pour ne jamais laisser le cockpit sans agent — l'erreur de config, elle,
    est signalée par ``manage.py check``.
    """
    configured = getattr(settings, "COCKPIT_AGENT_PRESETS", None) or []
    if not configured:
        return DEFAULT_AGENT_PRESETS
    presets = [p for p in (_preset_from_config(e) for e in configured) if p is not None]
    return presets or DEFAULT_AGENT_PRESETS


def presets_with_availability():
    """Chaque preset annoté de `(preset, available, reason)`.

    - headless : toujours disponible.
    - pty : disponible si le binaire est dans la liste blanche ET résolu sur le
      PATH de l'hôte (même règle que le manager). Sinon `available=False` avec une
      raison honnête : ``"unlisted"`` (hors liste blanche) ou ``"missing"``
      (autorisé mais introuvable sur l'hôte).
    """
    from apps.runtime.services.pane_manager import (
        CommandNotAllowed,
        resolve_allowed_binary,
    )

    allowed = set(getattr(settings, "COCKPIT_ALLOWED_CMDS", []))
    annotated = []
    for preset in get_agent_presets():
        if preset.kind == "headless":
            annotated.append((preset, True, ""))
            continue
        binary = preset.cmd.split()[0] if preset.cmd else ""
        if binary not in allowed:
            annotated.append((preset, False, "unlisted"))
            continue
        try:
            resolve_allowed_binary(binary)
            annotated.append((preset, True, ""))
        except CommandNotAllowed:
            annotated.append((preset, False, "missing"))
    return annotated
