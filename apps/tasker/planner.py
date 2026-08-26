"""Le Planner — Claude transforme un objectif en DAG de tâches.

Découpage volontaire : **tout ce qui peut être pur l'est**.

- ``build_prompt``  → texte, pur, testable
- ``parse_plan``    → JSON → structure validée, pur, **la pièce la plus testée**
- ``apply_plan``    → écrit les Task en base, pur DB
- ``request_plan``  → seule fonction async, elle orchestre les trois

Pourquoi cette obsession de pureté : un LLM renvoie parfois du JSON dans un
bloc markdown, parfois du texte avant, parfois un DAG cyclique. Toute cette
défense doit être testable **sans lancer Claude**. La partie non déterministe
se réduit à « va chercher du texte ».

Principe de refus : si le plan est invalide, on **refuse explicitement**. Pas de
« best effort » silencieux qui créerait des tâches à moitié fausses — un plan
faux distribué à n agents, c'est n fois le dégât.
"""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger("spacelabs.tasker")

MAX_TASKS = 24


class PlanError(Exception):
    """Plan inexploitable. Le message est montré à l'utilisateur."""


SYSTEM_RULES = (
    "Tu es un planificateur de travail logiciel. Découpe l'objectif en tâches "
    "indépendantes, exécutables chacune par un agent de code autonome.\n"
    "Réponds UNIQUEMENT par un objet JSON, sans texte autour, sans bloc markdown.\n"
    'Format exact : {"tasks": [{"key": "T1", "title": "...", '
    '"brief": "...", "depends_on": ["T0"]}]}\n'
    "Contraintes : au plus %d tâches ; « key » court et unique ; « brief » est "
    "la consigne complète envoyée à l'agent (il ne verra QUE ça) ; "
    "« depends_on » ne référence que des clés du même plan ; aucun cycle."
) % MAX_TASKS


def build_prompt(goal: str, feedback: str = "", existing=None) -> str:
    """Construit la demande de plan. ``existing`` sert au replan."""
    parts = [SYSTEM_RULES, "", f"OBJECTIF : {goal.strip()}"]
    if existing:
        done = [t for t in existing if t.status == "done"]
        failed = [t for t in existing if t.status in ("failed", "blocked")]
        parts.append("")
        parts.append("ÉTAT ACTUEL — ne replanifie que ce qui reste :")
        if done:
            parts.append("déjà fait : " + ", ".join(f"{t.key} {t.title}" for t in done))
        if failed:
            parts.append("en échec : " + ", ".join(f"{t.key} {t.title}" for t in failed))
    if feedback:
        parts += ["", f"CONSIGNE SUPPLÉMENTAIRE : {feedback.strip()}"]
    return "\n".join(parts)


def _extract_json(text: str) -> str:
    """Isole l'objet JSON d'une réponse qui peut être enrobée.

    Les modèles encadrent volontiers leur JSON de ```json … ``` ou d'une phrase
    d'introduction. On tolère ça (c'est du bruit de forme), mais rien de plus :
    on ne devine pas, on ne répare pas du JSON cassé.
    """
    if not text or not text.strip():
        raise PlanError("Le planificateur n'a rien répondu.")
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced:
        return fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise PlanError("Réponse du planificateur sans objet JSON.")
    return text[start : end + 1]


def parse_plan(text: str) -> list[dict]:
    """Valide de bout en bout. Lève ``PlanError`` au moindre doute."""
    try:
        data = json.loads(_extract_json(text))
    except json.JSONDecodeError as exc:
        raise PlanError(f"JSON invalide : {exc.msg}") from exc

    if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
        raise PlanError("Le plan doit être un objet avec une liste « tasks ».")
    raw = data["tasks"]
    if not raw:
        raise PlanError("Le plan ne contient aucune tâche.")
    if len(raw) > MAX_TASKS:
        raise PlanError(f"Plan trop gros ({len(raw)} tâches, maximum {MAX_TASKS}).")

    tasks, seen = [], set()
    for i, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise PlanError(f"Tâche {i} : ce n'est pas un objet.")
        key = str(item.get("key") or "").strip()
        title = str(item.get("title") or "").strip()
        if not key:
            raise PlanError(f"Tâche {i} : « key » manquante.")
        if not re.fullmatch(r"[\w.-]{1,12}", key):
            raise PlanError(f"Clé « {key} » invalide (12 caractères max, sans espace).")
        if key in seen:
            raise PlanError(f"Clé « {key} » en double.")
        seen.add(key)
        if not title:
            raise PlanError(f"Tâche {key} : « title » manquant.")
        deps = item.get("depends_on") or []
        if isinstance(deps, str):
            deps = [deps]
        if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
            raise PlanError(f"Tâche {key} : « depends_on » doit être une liste de clés.")
        tasks.append({
            "key": key,
            "title": title[:200],
            "brief": str(item.get("brief") or title).strip(),
            "depends_on": [d.strip() for d in deps if d.strip()],
        })

    for t in tasks:
        for dep in t["depends_on"]:
            if dep not in seen:
                raise PlanError(f"Tâche {t['key']} dépend de « {dep} », qui n'existe pas.")
            if dep == t["key"]:
                raise PlanError(f"Tâche {t['key']} dépend d'elle-même.")
    _reject_cycles(tasks)
    return tasks


def _reject_cycles(tasks: list[dict]) -> None:
    """Un cycle bloquerait le DAG pour toujours : aucune tâche ne deviendrait
    jamais prête, et la mission resterait « en cours » sans rien faire. On le
    détecte ici plutôt que de le découvrir en production."""
    deps = {t["key"]: set(t["depends_on"]) for t in tasks}
    resolved: set[str] = set()
    while True:
        ready = {k for k, d in deps.items() if k not in resolved and d <= resolved}
        if not ready:
            break
        resolved |= ready
    stuck = set(deps) - resolved
    if stuck:
        raise PlanError("Dépendances circulaires entre : " + ", ".join(sorted(stuck)))


def apply_plan(mission, tasks: list[dict], replace: bool = False) -> list:
    """Écrit le plan en base. Les dépendances sont résolues par clé.

    ``replace`` n'efface que les tâches **non commencées** : on ne détruit
    jamais un travail déjà fait ou en cours au motif qu'on replanifie.
    """
    from .models import Task

    if replace:
        mission.tasks.filter(status__in=[Task.Status.TODO, Task.Status.READY]).delete()

    existing = {t.key: t for t in mission.tasks.all()}
    created = []
    base_order = mission.tasks.count()
    for i, data in enumerate(tasks):
        if data["key"] in existing:
            continue                      # replan : on ne recrée pas l'existant
        task = Task.objects.create(
            mission=mission, key=data["key"], title=data["title"],
            brief=data["brief"], order=base_order + i,
        )
        existing[task.key] = task
        created.append((task, data["depends_on"]))

    for task, dep_keys in created:
        deps = [existing[k] for k in dep_keys if k in existing]
        if deps:
            task.depends_on.set(deps)
    logger.info("tasker: plan appliqué — %d tâche(s) créée(s)", len(created))
    return [t for t, _ in created]


async def request_plan(mission, feedback: str = "", ask=None) -> list:
    """Demande un plan à Claude, le valide, l'applique.

    ``ask`` est injectable : les tests fournissent un texte canné et vérifient
    tout le pipeline sans lancer de binaire. En production, c'est la session
    headless du pane planificateur.
    """
    from asgiref.sync import sync_to_async

    ask = ask or _ask_via_headless
    existing = await sync_to_async(lambda: list(mission.tasks.all()))()
    prompt = build_prompt(mission.goal, feedback=feedback, existing=existing)
    text = await ask(mission, prompt)
    tasks = parse_plan(text)              # lève PlanError si douteux
    return await sync_to_async(apply_plan)(mission, tasks)


def collect_text(rows) -> str:
    """Extrait le texte d'assistant d'une suite d'événements normalisés.

    Forme réelle produite par ``apps.chat.events.normalize`` :
    ``{"kind": "assistant", "blocks": [{"type": "text", "text": "..."}, ...]}``.
    Les blocs ``tool_use`` sont ignorés — on ne veut que la prose.
    """
    chunks: list[str] = []
    for etype, norm in rows:
        if etype != "assistant" or not isinstance(norm, dict):
            continue
        for block in norm.get("blocks") or []:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text") or ""
                if isinstance(text, str) and text.strip():
                    chunks.append(text)
    return "\n".join(chunks)


async def _ask_via_headless(mission, prompt: str) -> str:
    """Envoie la demande au pane planificateur et récupère sa réponse.

    Le planificateur est un pane headless (ADR-2) : reprise, coût et EventLog
    sont déjà gérés. On lit la réponse dans EventLog — la source durable — et
    on s'arrête au premier ``result``, qui marque la fin du tour.
    """
    import asyncio

    from asgiref.sync import sync_to_async
    from django.conf import settings

    from apps.chat.models import EventLog
    from apps.runtime.services.headless_manager import HeadlessManager

    pane = await sync_to_async(lambda: mission.planner_pane)()
    if pane is None:
        raise PlanError("Aucun pane planificateur pour cette mission.")

    headless = HeadlessManager.get()
    pane_id = str(pane.pk)
    owner_id = await sync_to_async(lambda: mission.workspace.owner_id)()
    cwd = await sync_to_async(pane.effective_cwd)()
    if pane_id not in headless.sessions or headless.sessions[pane_id].status != "running":
        await headless.start(pane_id, owner_id=owner_id, cwd=cwd)

    watermark = await sync_to_async(
        lambda: EventLog.objects.filter(pane=pane).order_by("-seq").values_list("seq", flat=True).first() or 0
    )()
    await headless.send(pane_id, prompt, owner_id=owner_id)

    timeout = float(getattr(settings, "COCKPIT_TASKER_PLAN_TIMEOUT_SECONDS", 120))
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.4)
        rows = await sync_to_async(
            lambda: list(
                EventLog.objects.filter(pane=pane, seq__gt=watermark)
                .order_by("seq")
                .values_list("event_type", "normalized")
            )
        )()
        if any(etype == "result" for etype, _ in rows):
            return collect_text(rows)
    raise PlanError("Le planificateur n'a pas répondu dans le délai imparti.")
