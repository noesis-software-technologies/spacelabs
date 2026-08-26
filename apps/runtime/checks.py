"""Contrôles de configuration au démarrage (django.core.checks).

Une mauvaise configuration ne doit pas se découvrir en production sous la forme
d'un serveur qui gonfle jusqu'à l'OOM. ``manage.py check`` la signale avant.
"""
from django.conf import settings
from django.core.checks import Error, Warning, register

# Au-delà, le seul budget des tampons de sortie devient déraisonnable pour un
# poste de travail : 16 agents × 200 ko = 3,2 Mo, ça va ; × 20 Mo, non.
BUFFER_BUDGET_WARN = 64 * 1024 * 1024      # 64 Mo
BUFFER_BUDGET_ERROR = 512 * 1024 * 1024    # 512 Mo


@register()
def check_buffer_budget(app_configs, **kwargs):
    """Budget mémoire des tampons = BUFFER_BYTES × plafond d'agents.

    Chaque pane garde un tampon circulaire de sa sortie pour pouvoir rejouer
    l'écran à la reconnexion. Le coût est donc multiplié par le nombre d'agents
    autorisés — c'est le produit qu'il faut regarder, pas chaque réglage.
    """
    per_pane = int(getattr(settings, "COCKPIT_BUFFER_BYTES", 0))
    max_panes = int(getattr(settings, "COCKPIT_MAX_PANES", 0))
    total = per_pane * max_panes
    if total >= BUFFER_BUDGET_ERROR:
        return [Error(
            f"Budget mémoire des tampons irréaliste : {per_pane} o × {max_panes} agents "
            f"= {total / 1048576:.0f} Mo.",
            hint="Baisse COCKPIT_BUFFER_BYTES ou COCKPIT_MAX_PANES.",
            id="runtime.E001",
        )]
    if total >= BUFFER_BUDGET_WARN:
        return [Warning(
            f"Budget mémoire des tampons élevé : {total / 1048576:.0f} Mo "
            f"({per_pane} o × {max_panes} agents).",
            hint="Vérifie que la machine encaisse ce pic avec tous les agents actifs.",
            id="runtime.W001",
        )]
    return []


@register()
def check_command_allowlist(app_configs, **kwargs):
    """La liste blanche ne doit contenir que des noms nus."""
    problems = []
    for cmd in getattr(settings, "COCKPIT_ALLOWED_CMDS", []):
        if "/" in cmd or "\\" in cmd or cmd.startswith("~"):
            problems.append(Error(
                f"COCKPIT_ALLOWED_CMDS contient un chemin : « {cmd} ».",
                hint="Mets un nom de binaire nu ; la résolution passe par le PATH.",
                id="runtime.E002",
            ))
    return problems


@register()
def check_agent_presets(app_configs, **kwargs):
    """Valide COCKPIT_AGENT_PRESETS : liste d'objets, kind connu, cmd pour pty.

    Une entrée mal formée ne casse pas le démarrage (le chargeur l'ignore), mais
    disparaître en silence serait pire qu'un avertissement : on la signale ici.
    """
    configured = getattr(settings, "COCKPIT_AGENT_PRESETS", None)
    if not configured:
        return []
    if not isinstance(configured, list):
        return [Error(
            "COCKPIT_AGENT_PRESETS doit être une liste d'objets.",
            hint='Ex. : [{"key": "claude", "label": "Claude Code", "cmd": "claude"}]',
            id="runtime.E003",
        )]
    problems = []
    for i, entry in enumerate(configured):
        if not isinstance(entry, dict):
            problems.append(Warning(
                f"COCKPIT_AGENT_PRESETS[{i}] ignoré : ce n'est pas un objet.",
                id="runtime.W002",
            ))
            continue
        key = str(entry.get("key", "")).strip()
        label = str(entry.get("label", "")).strip()
        kind = str(entry.get("kind", "pty")).strip() or "pty"
        cmd = str(entry.get("cmd", "")).strip()
        if not key or not label:
            problems.append(Warning(
                f"COCKPIT_AGENT_PRESETS[{i}] ignoré : « key » et « label » sont requis.",
                id="runtime.W002",
            ))
        elif kind not in {"pty", "headless"}:
            problems.append(Warning(
                f"COCKPIT_AGENT_PRESETS[{i}] (« {label} ») ignoré : kind « {kind} » inconnu.",
                hint="kind doit valoir « pty » ou « headless ».",
                id="runtime.W002",
            ))
        elif kind == "pty" and not cmd:
            problems.append(Warning(
                f"COCKPIT_AGENT_PRESETS[{i}] (« {label} ») ignoré : un preset pty exige « cmd ».",
                id="runtime.W002",
            ))
    return problems
