"""Mise en page du graphe de mission — pure, donc testable sans rendu.

Le Swarm affiche le DAG d'une mission : qui dépend de qui, qui tourne, qui a
fini. C'est de la **lecture seule** — on ne pilote pas une mission depuis le
graphe, on la comprend.

Choix de disposition : **par niveau de dépendance**, pas en éventail décoratif.
Le niveau d'une tâche est la longueur du plus long chemin depuis une racine :
tout ce qui est sur la même colonne peut tourner en parallèle. La forme du
graphe raconte donc directement le parallélisme réel de la mission.

Coordonnées en **pourcentages** : le SVG s'adapte à la taille du dock ou du
plein écran sans recalcul côté serveur.
"""
from __future__ import annotations

from dataclasses import dataclass, field

MAX_NODES = 60          # au-delà, un graphe n'est plus lisible : on renvoie une liste


@dataclass
class Node:
    key: str
    title: str
    status: str
    level: int
    x: float
    y: float
    agent: str = ""

    @property
    def style(self) -> str:
        """Position CSS prête à l'emploi, en NOTATION ANGLAISE.

        Trouvé en test réel : Django localise les nombres (L10N), et en
        français « 8.0 » devient « 8,0 ». Le CSS « left: 8,0% » est invalide —
        tous les nœuds s'empilaient au même endroit. On formate donc ici, en
        Python, où la virgule décimale ne peut pas s'inviter.
        """
        return f"left: {self.x:.2f}%; top: {self.y:.2f}%"

    @property
    def state(self) -> str:
        """Classe visuelle — même sémantique de couleur que les panes."""
        return {
            "done": "done", "running": "active", "failed": "failed",
            "blocked": "failed", "review": "review",
        }.get(self.status, "idle")


@dataclass
class Graph:
    nodes: list[Node] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)
    levels: int = 0
    too_large: bool = False

    def by_key(self, key: str) -> Node | None:
        return next((n for n in self.nodes if n.key == key), None)


def compute_levels(tasks) -> dict[str, int]:
    """Niveau = plus long chemin depuis une racine.

    Résolution itérative plutôt que récursive : un DAG issu de la base peut
    contenir un cycle (le planificateur les refuse, mais une tâche créée à la
    main, non). On s'arrête alors proprement au lieu de boucler à l'infini —
    les nœuds restants sont posés au dernier niveau.
    """
    deps = {t.key: [d.key for d in t.depends_on.all()] for t in tasks}
    levels: dict[str, int] = {}
    for _ in range(len(deps) + 1):
        progress = False
        for key, parents in deps.items():
            if key in levels:
                continue
            known = [levels[p] for p in parents if p in levels]
            if len(known) == len(parents):
                levels[key] = (max(known) + 1) if known else 0
                progress = True
        if not progress:
            break
    stuck = [k for k in deps if k not in levels]
    if stuck:
        fallback = (max(levels.values()) + 1) if levels else 0
        for key in stuck:
            levels[key] = fallback
    return levels


def build(tasks) -> Graph:
    """Construit le graphe positionné d'une liste de tâches."""
    tasks = list(tasks)
    if not tasks:
        return Graph()
    if len(tasks) > MAX_NODES:
        return Graph(too_large=True)

    levels = compute_levels(tasks)
    depth = max(levels.values()) + 1
    columns: dict[int, list] = {}
    for task in sorted(tasks, key=lambda t: (levels[t.key], t.order, t.pk)):
        columns.setdefault(levels[task.key], []).append(task)

    nodes: list[Node] = []
    for level, column in columns.items():
        # Réparti verticalement, centré : une colonne d'un seul nœud est au milieu.
        count = len(column)
        for i, task in enumerate(column):
            x = 8 + (level * (84 / max(1, depth - 1))) if depth > 1 else 50
            y = (100 / (count + 1)) * (i + 1)
            agent = ""
            assignment = task.assignments.first() if hasattr(task, "assignments") else None
            if assignment is not None and assignment.pane_id:
                agent = assignment.pane.kind
            nodes.append(Node(
                key=task.key, title=task.title, status=task.status,
                level=level, x=round(x, 2), y=round(y, 2), agent=agent,
            ))

    keys = {n.key for n in nodes}
    edges = [
        (dep.key, task.key)
        for task in tasks
        for dep in task.depends_on.all()
        if dep.key in keys and task.key in keys
    ]
    return Graph(nodes=nodes, edges=edges, levels=depth)


def edge_path(graph: Graph, src: str, dst: str) -> str:
    """Courbe de Bézier horizontale entre deux nœuds (coordonnées en %)."""
    a, b = graph.by_key(src), graph.by_key(dst)
    if a is None or b is None:
        return ""
    mid = (a.x + b.x) / 2
    return f"M {a.x} {a.y} C {mid} {a.y}, {mid} {b.y}, {b.x} {b.y}"
