"""S12 — le Planner. L'essentiel des tests porte sur le REFUS.

Un plan faux distribué à n agents, c'est n fois le dégât. La partie non
déterministe (aller chercher du texte) est injectable ; tout le reste est pur
et testé sans lancer de binaire.
"""
import pytest
from django.contrib.auth import get_user_model

from apps.tasker.models import Mission, Task
from apps.tasker.planner import (
    MAX_TASKS,
    PlanError,
    apply_plan,
    build_prompt,
    parse_plan,
    request_plan,
)
from apps.workspaces.models import HeadlessPane, Pane, Workspace

User = get_user_model()


@pytest.fixture
def mission(db):
    u = User.objects.create_user(username="pilote", password="x")
    ws = Workspace.objects.create(owner=u, name="W", cwd="/tmp")
    return Mission.objects.create(workspace=ws, goal="ajouter des tests au module auth")


GOOD = """{"tasks": [
  {"key": "T1", "title": "extraire les fixtures", "brief": "sors les fixtures partagées"},
  {"key": "T2", "title": "tester le refresh", "brief": "couvre la rotation", "depends_on": ["T1"]}
]}"""


# ── Acceptation ───────────────────────────────────────────────────────────────
def test_parses_a_clean_plan():
    tasks = parse_plan(GOOD)
    assert [t["key"] for t in tasks] == ["T1", "T2"]
    assert tasks[1]["depends_on"] == ["T1"]


def test_tolerates_markdown_fences_and_chatter():
    """Les modèles enrobent souvent leur JSON : c'est du bruit de forme."""
    wrapped = "Voici le plan :\n```json\n" + GOOD + "\n```\nBon courage !"
    assert len(parse_plan(wrapped)) == 2


def test_depends_on_accepts_a_bare_string():
    plan = '{"tasks": [{"key":"A","title":"a"},{"key":"B","title":"b","depends_on":"A"}]}'
    assert parse_plan(plan)[1]["depends_on"] == ["A"]


def test_brief_defaults_to_title_when_absent():
    assert parse_plan('{"tasks":[{"key":"A","title":"faire le café"}]}')[0]["brief"] == "faire le café"


# ── Refus — le cœur du sprint ─────────────────────────────────────────────────
@pytest.mark.parametrize(
    "payload, needle",
    [
        ("", "rien répondu"),
        ("je ne peux pas vous aider", "sans objet JSON"),
        ("{ceci n'est pas du json}", "JSON invalide"),
        ('{"plan": []}', "liste « tasks »"),
        ('{"tasks": []}', "aucune tâche"),
        ('{"tasks": [{"title": "sans clé"}]}', "manquante"),
        ('{"tasks": [{"key": "A", "title": ""}]}', "manquant"),
        ('{"tasks": [{"key": "A B C D E F G H", "title": "x"}]}', "invalide"),
        ('{"tasks": [{"key":"A","title":"x"},{"key":"A","title":"y"}]}', "double"),
        ('{"tasks": [{"key":"A","title":"x","depends_on":["ZZ"]}]}', "n'existe pas"),
        ('{"tasks": [{"key":"A","title":"x","depends_on":["A"]}]}', "elle-même"),
        ('{"tasks": [{"key":"A","title":"x","depends_on":{"a":1}}]}', "liste de clés"),
        ('{"tasks": ["pas un objet"]}', "pas un objet"),
    ],
)
def test_refuses_a_doubtful_plan(payload, needle):
    with pytest.raises(PlanError) as exc:
        parse_plan(payload)
    assert needle in str(exc.value)


def test_refuses_a_cyclic_dag():
    """Un cycle bloquerait le DAG pour toujours : aucune tâche ne serait prête."""
    cyclic = ('{"tasks": [{"key":"A","title":"a","depends_on":["B"]},'
              '{"key":"B","title":"b","depends_on":["A"]}]}')
    with pytest.raises(PlanError, match="circulaires"):
        parse_plan(cyclic)


def test_refuses_a_three_node_cycle():
    plan = ('{"tasks": [{"key":"A","title":"a","depends_on":["C"]},'
            '{"key":"B","title":"b","depends_on":["A"]},'
            '{"key":"C","title":"c","depends_on":["B"]}]}')
    with pytest.raises(PlanError, match="circulaires"):
        parse_plan(plan)


def test_refuses_an_oversized_plan():
    items = ",".join(f'{{"key":"T{i}","title":"t{i}"}}' for i in range(MAX_TASKS + 1))
    with pytest.raises(PlanError, match="trop gros"):
        parse_plan('{"tasks": [' + items + "]}")


# ── Application en base ───────────────────────────────────────────────────────
@pytest.mark.django_db
def test_apply_plan_creates_the_dag(mission):
    created = apply_plan(mission, parse_plan(GOOD))
    assert len(created) == 2
    t2 = mission.tasks.get(key="T2")
    assert [d.key for d in t2.depends_on.all()] == ["T1"]


@pytest.mark.django_db
def test_apply_plan_is_idempotent_on_existing_keys(mission):
    apply_plan(mission, parse_plan(GOOD))
    again = apply_plan(mission, parse_plan(GOOD))
    assert again == [], "une clé déjà présente ne doit pas être recréée"
    assert mission.tasks.count() == 2


@pytest.mark.django_db
def test_replace_never_destroys_started_work(mission):
    """Replanifier ne doit pas effacer ce qui est fait ou en cours."""
    apply_plan(mission, parse_plan(GOOD))
    done = mission.tasks.get(key="T1")
    done.status = Task.Status.DONE
    done.save(update_fields=["status"])

    apply_plan(mission, [{"key": "T3", "title": "neuf", "brief": "b", "depends_on": []}], replace=True)

    keys = set(mission.tasks.values_list("key", flat=True))
    assert "T1" in keys, "une tâche terminée a été supprimée"
    assert "T3" in keys
    assert "T2" not in keys, "une tâche non commencée devait être remplacée"


# ── Le prompt ─────────────────────────────────────────────────────────────────
def test_prompt_states_the_goal_and_demands_json():
    prompt = build_prompt("migrer les tests")
    assert "migrer les tests" in prompt
    assert "JSON" in prompt


@pytest.mark.django_db
def test_replan_prompt_carries_current_state(mission):
    apply_plan(mission, parse_plan(GOOD))
    t = mission.tasks.get(key="T1")
    t.status = Task.Status.DONE
    t.save(update_fields=["status"])

    prompt = build_prompt(mission.goal, feedback="évite les mocks", existing=list(mission.tasks.all()))
    assert "déjà fait" in prompt and "T1" in prompt
    assert "évite les mocks" in prompt


# ── request_plan de bout en bout, avec un « ask » injecté ─────────────────────
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_request_plan_applies_what_claude_returned():
    u = await User.objects.acreate(username="p")
    ws = await Workspace.objects.acreate(owner=u, name="W", cwd="/tmp")
    m = await Mission.objects.acreate(workspace=ws, goal="objectif")

    async def fake_ask(mission, prompt):
        assert "objectif" in prompt
        return GOOD

    created = await request_plan(m, ask=fake_ask)
    assert len(created) == 2
    assert await m.tasks.acount() == 2


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_request_plan_creates_nothing_when_the_answer_is_bad():
    """Refus explicite : surtout pas de création partielle."""
    u = await User.objects.acreate(username="p2")
    ws = await Workspace.objects.acreate(owner=u, name="W", cwd="/tmp")
    m = await Mission.objects.acreate(workspace=ws, goal="objectif")

    async def bad_ask(mission, prompt):
        return "désolé, je ne sais pas faire"

    with pytest.raises(PlanError):
        await request_plan(m, ask=bad_ask)
    assert await m.tasks.acount() == 0


# ── Le pane planificateur n'est pas un agent de travail ───────────────────────
@pytest.mark.django_db
def test_planner_pane_is_never_given_a_task(mission):
    from apps.tasker.services import eligible_panes

    HeadlessPane.objects.create(
        workspace=mission.workspace, status=Pane.Status.RUNNING, is_system=True
    )
    assert eligible_panes(mission) == []

    worker = HeadlessPane.objects.create(
        workspace=mission.workspace, status=Pane.Status.RUNNING
    )
    assert [p.pk for p in eligible_panes(mission)] == [worker.pk]


@pytest.mark.django_db
def test_planner_pane_is_hidden_from_the_grid(client, mission):
    """Il consomme une session, mais il n'a rien à faire dans la grille."""
    HeadlessPane.objects.create(
        workspace=mission.workspace, status=Pane.Status.RUNNING, is_system=True, title="Planner"
    )
    client.force_login(mission.workspace.owner)
    html = client.get(f"/cockpit/{mission.workspace.slug}/").content.decode()
    assert "Planner" not in html


# ── Régression : l'extraction doit suivre la forme RÉELLE des événements ──────
def test_collect_text_reads_the_real_assistant_shape():
    """Bug trouvé en live : je lisais `norm["text"]`, alors que normalize()
    produit `{"kind":"assistant","blocks":[{"type":"text","text":...}]}`.
    Le planificateur recevait donc toujours une réponse vide."""
    from apps.tasker.planner import collect_text

    rows = [
        ("system", {"kind": "system"}),
        ("assistant", {"kind": "assistant", "blocks": [{"type": "text", "text": '{"tasks":'}]}),
        ("assistant", {"kind": "assistant", "blocks": [
            {"type": "tool_use", "name": "Read", "input": {}},
            {"type": "text", "text": '[{"key":"T1","title":"x"}]}'},
        ]}),
        ("result", {"kind": "result", "cost_usd": 0.1}),
    ]
    text = collect_text(rows)
    assert parse_plan(text)[0]["key"] == "T1"


def test_collect_text_ignores_tool_use_only_events():
    from apps.tasker.planner import collect_text

    assert collect_text([("assistant", {"blocks": [{"type": "tool_use", "name": "Bash"}]})]) == ""
