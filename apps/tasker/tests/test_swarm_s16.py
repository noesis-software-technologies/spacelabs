import re
"""S16 — le graphe de mission et le plafond de la vue télé.

La mise en page est pure : on peut vérifier la topologie sans rendre un pixel.
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.tasker.graph import MAX_NODES, build, compute_levels, edge_path
from apps.tasker.models import Mission, Task
from apps.workspaces.models import HeadlessPane, Pane, Workspace

User = get_user_model()


@pytest.fixture
def mission(db):
    u = User.objects.create_user(username="pilote", password="x")
    ws = Workspace.objects.create(owner=u, name="W", cwd="/tmp")
    return Mission.objects.create(workspace=ws, goal="objectif")


def _t(mission, key, deps=(), status=Task.Status.TODO, order=0):
    task = Task.objects.create(mission=mission, key=key, title=f"tâche {key}",
                               status=status, order=order)
    if deps:
        task.depends_on.set(deps)
    return task


# ── Niveaux de dépendance ─────────────────────────────────────────────────────
@pytest.mark.django_db
def test_independent_tasks_share_level_zero(mission):
    """Même colonne = peut tourner en parallèle. C'est ce que le graphe raconte."""
    a, b, c = _t(mission, "A"), _t(mission, "B"), _t(mission, "C")
    levels = compute_levels([a, b, c])
    assert set(levels.values()) == {0}


@pytest.mark.django_db
def test_a_chain_produces_increasing_levels(mission):
    a = _t(mission, "A")
    b = _t(mission, "B", deps=[a])
    c = _t(mission, "C", deps=[b])
    levels = compute_levels([a, b, c])
    assert (levels["A"], levels["B"], levels["C"]) == (0, 1, 2)


@pytest.mark.django_db
def test_level_is_the_longest_path_not_the_shortest(mission):
    """D dépend de A (court) et de C (long) : il doit passer APRÈS les deux."""
    a = _t(mission, "A")
    b = _t(mission, "B", deps=[a])
    c = _t(mission, "C", deps=[b])
    d = _t(mission, "D", deps=[a, c])
    levels = compute_levels([a, b, c, d])
    assert levels["D"] == 3


@pytest.mark.django_db
def test_a_cycle_does_not_hang_the_layout(mission):
    """Le planificateur refuse les cycles, mais une tâche créée à la main peut
    en introduire un. La mise en page doit s'arrêter, pas boucler."""
    a = _t(mission, "A")
    b = _t(mission, "B", deps=[a])
    a.depends_on.set([b])          # cycle A → B → A
    levels = compute_levels([a, b])
    assert set(levels) == {"A", "B"}, "tous les nœuds doivent être placés"


# ── Construction du graphe ────────────────────────────────────────────────────
@pytest.mark.django_db
def test_empty_mission_gives_an_empty_graph(mission):
    graph = build([])
    assert graph.nodes == [] and graph.edges == []


@pytest.mark.django_db
def test_nodes_carry_position_and_state(mission):
    a = _t(mission, "A", status=Task.Status.RUNNING)
    _t(mission, "B", deps=[a], status=Task.Status.DONE)
    graph = build(list(mission.tasks.all()))

    assert len(graph.nodes) == 2
    assert graph.by_key("A").state == "active"
    assert graph.by_key("B").state == "done"
    for node in graph.nodes:
        assert 0 <= node.x <= 100 and 0 <= node.y <= 100


@pytest.mark.django_db
def test_blocked_and_failed_read_as_failed(mission):
    _t(mission, "A", status=Task.Status.BLOCKED)
    _t(mission, "B", status=Task.Status.FAILED)
    graph = build(list(mission.tasks.all()))
    assert {n.state for n in graph.nodes} == {"failed"}


@pytest.mark.django_db
def test_parallel_tasks_do_not_overlap(mission):
    """Trois tâches indépendantes : même colonne, hauteurs distinctes."""
    for k in "ABC":
        _t(mission, k)
    graph = build(list(mission.tasks.all()))
    xs = {n.x for n in graph.nodes}
    ys = {n.y for n in graph.nodes}
    assert len(xs) == 1, "elles sont au même niveau"
    assert len(ys) == 3, "elles doivent être réparties verticalement"


@pytest.mark.django_db
def test_dependencies_flow_left_to_right(mission):
    a = _t(mission, "A")
    _t(mission, "B", deps=[a])
    graph = build(list(mission.tasks.all()))
    assert graph.by_key("A").x < graph.by_key("B").x


@pytest.mark.django_db
def test_edges_mirror_the_dependencies(mission):
    a = _t(mission, "A")
    _t(mission, "B", deps=[a])
    graph = build(list(mission.tasks.all()))
    assert graph.edges == [("A", "B")]


@pytest.mark.django_db
def test_edge_path_is_a_bezier_between_the_two_nodes(mission):
    a = _t(mission, "A")
    _t(mission, "B", deps=[a])
    graph = build(list(mission.tasks.all()))
    path = edge_path(graph, "A", "B")
    assert path.startswith("M ") and " C " in path


@pytest.mark.django_db
def test_edge_path_of_an_unknown_node_is_empty(mission):
    graph = build([_t(mission, "A")])
    assert edge_path(graph, "A", "ZZ") == ""


@pytest.mark.django_db
def test_a_huge_mission_falls_back_instead_of_drawing_mush(mission):
    tasks = [_t(mission, f"T{i}") for i in range(MAX_NODES + 1)]
    graph = build(tasks)
    assert graph.too_large is True and graph.nodes == []


# ── La vue ────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_swarm_view_renders_the_graph(client, mission):
    a = _t(mission, "A", status=Task.Status.RUNNING)
    _t(mission, "B", deps=[a])
    client.force_login(mission.workspace.owner)
    html = client.get(f"/missions/{mission.pk}/swarm/").content.decode()
    assert 'class="swarm-node"' in html
    assert 'data-state="active"' in html
    assert "swarm-edge" in html


@pytest.mark.django_db
def test_swarm_view_is_scoped_to_its_owner(client, mission):
    other = User.objects.create_user(username="autre", password="x")
    client.force_login(other)
    assert client.get(f"/missions/{mission.pk}/swarm/").status_code == 404


# ── Vue télé : plafond de lisibilité ──────────────────────────────────────────
@pytest.mark.django_db
def test_observer_caps_tiles_and_says_how_many_are_hidden(client, mission):
    """Un mur de 16 agents n'est pas lisible à trois mètres."""
    from apps.observer.models import ObserverSettings
    # Le plafond est configurable depuis le commit full-matrix
    # (COCKPIT_OBSERVER_MAX_TILES) : on lit le réglage effectif au lieu
    # d'une constante figée, volontairement supprimée.
    from apps.observer.views import _observer_max_tiles, _public_grid_context

    owner = mission.workspace.owner
    s = ObserverSettings.for_owner(owner)
    s.live = True
    s.save(update_fields=["live"])
    for _ in range(14):
        HeadlessPane.objects.create(workspace=mission.workspace, is_public=True)

    cap = _observer_max_tiles()
    context = _public_grid_context()
    assert len(context["items"]) == cap
    assert context["hidden_count"] == 14 - cap

    html = client.get(reverse("observer:grid")).content.decode()
    assert "non affiché" in html


@pytest.mark.django_db
def test_observer_shows_working_agents_first(mission):
    """Ce qui travaille passe devant ce qui dort."""
    from apps.observer.models import ObserverSettings
    from apps.observer.views import _public_grid_context

    s = ObserverSettings.for_owner(mission.workspace.owner)
    s.live = True
    s.save(update_fields=["live"])
    for _ in range(9):
        HeadlessPane.objects.create(workspace=mission.workspace, is_public=True)
    busy = HeadlessPane.objects.create(
        workspace=mission.workspace, is_public=True, status=Pane.Status.RUNNING
    )

    ids = [item["id"] for item in _public_grid_context()["items"]]
    assert busy.pk in ids, "l'agent qui travaille a été évincé par des agents au repos"


@pytest.mark.django_db
def test_observer_without_overflow_says_nothing(client, mission):
    from apps.observer.models import ObserverSettings

    s = ObserverSettings.for_owner(mission.workspace.owner)
    s.live = True
    s.save(update_fields=["live"])
    HeadlessPane.objects.create(workspace=mission.workspace, is_public=True)
    html = client.get(reverse("observer:grid")).content.decode()
    assert "non affiché" not in html


# ── Trouvé sur serveur réel : la locale cassait le CSS ────────────────────────
@pytest.mark.django_db
def test_node_style_uses_a_decimal_point_not_a_comma(mission):
    """Django localise les nombres : en français « 8.0 » devient « 8,0 » et
    « left: 8,0% » est du CSS invalide — tous les nœuds s'empilaient."""
    _t(mission, "A")
    node = build(list(mission.tasks.all())).nodes[0]
    assert "," not in node.style
    assert node.style.startswith("left: ") and "%" in node.style


@pytest.mark.django_db
def test_rendered_positions_are_valid_css(client, mission):
    a = _t(mission, "A")
    _t(mission, "B", deps=[a])
    client.force_login(mission.workspace.owner)
    html = client.get(f"/missions/{mission.pk}/swarm/").content.decode()
    styles = re.findall(r'style="(left: [^"]+)"', html)
    assert styles, "aucune position rendue"
    for style in styles:
        assert "," not in style, f"CSS localisé, donc invalide : {style}"


@pytest.mark.django_db
def test_edge_paths_are_not_localised(client, mission):
    a = _t(mission, "A")
    _t(mission, "B", deps=[a])
    client.force_login(mission.workspace.owner)
    html = client.get(f"/missions/{mission.pk}/swarm/").content.decode()
    for d in re.findall(r'<path class="swarm-edge"[^>]*d="([^"]+)"', html):
        assert "," in d, "une courbe de Bézier contient des virgules de séparation"
        assert not re.search(r"\d,\d", d.replace(", ", " ")), f"nombre localisé : {d}"
