"""Application d'une skill à un agent."""
from __future__ import annotations

import logging

logger = logging.getLogger("spacelabs.skills")


class SkillError(Exception):
    """Refus explicite, montré à l'utilisateur."""


async def apply_to_pane(skill, pane) -> str:
    """Envoie le corps de la skill à l'agent, quel que soit son type.

    Le pane doit déjà tourner : démarrer un agent est une décision de
    l'utilisateur, pas un effet de bord d'un glisser-déposer.
    """
    from apps.workspaces.models import registry

    entry = registry.get(pane.kind)
    if entry is None or not entry.dispatch_path:
        raise SkillError(f"Le type « {pane.kind} » ne sait pas recevoir de consigne.")
    await entry.dispatch(pane, skill.body)
    logger.info("skill %s appliquée au pane %s", skill.pk, pane.pk)
    return f"« {skill.name} » envoyée à {pane.title or pane.kind}."


BUILTINS = [
    {
        "name": "BridgeSecurity",
        "tag": "security",
        "description": "Revue sécurité : OWASP Top 10, CWE Top 25, chaîne d'approvisionnement.",
        "body": (
            "Fais une revue de sécurité du code que tu viens de toucher. "
            "Couvre l'OWASP Top 10 et le CWE Top 25, et vérifie les dépendances "
            "ajoutées. Ne lis ni n'affiche jamais de fichier .env. "
            "Rends un rapport court : constat, gravité, correctif proposé."
        ),
    },
    {
        "name": "BridgeGithub",
        "tag": "workflow",
        "description": "Commit propre et push : conventional commit, un seul sujet.",
        "body": (
            "Stage les changements locaux du dépôt courant, écris un commit "
            "conventionnel (type(scope): sujet à l'impératif, corps expliquant le "
            "pourquoi), puis pousse. Un seul sujet par commit ; si le diff en "
            "couvre plusieurs, découpe-le."
        ),
    },
    {
        "name": "BridgeTests",
        "tag": "workflow",
        "description": "Écrit les tests manquants avant de déclarer terminé.",
        "body": (
            "Identifie ce qui n'est pas couvert dans le code que tu viens "
            "d'écrire, puis ajoute les tests manquants. Un test par comportement, "
            "nommé d'après ce qu'il prouve. Lance la suite et ne dis pas "
            "« terminé » tant qu'elle n'est pas verte."
        ),
    },
    {
        "name": "BridgeMemory",
        "tag": "memory",
        "description": "Consigne les décisions durables dans la mémoire projet.",
        "body": (
            "Relis ce qui vient d'être décidé et consigne-le dans les notes du "
            "projet : la décision, l'alternative écartée, et la raison. Une note "
            "par décision, datée."
        ),
    },
]


def ensure_builtins() -> int:
    """Crée les skills fournies avec le produit. Idempotent."""
    from .models import Skill

    created = 0
    for i, data in enumerate(BUILTINS):
        _, made = Skill.objects.get_or_create(
            name=data["name"], is_builtin=True,
            defaults={**{k: v for k, v in data.items() if k != "name"}, "order": i},
        )
        created += int(made)
    return created
