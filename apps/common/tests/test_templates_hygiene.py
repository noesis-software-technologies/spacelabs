"""Garde-fou : aucun commentaire de template.

Pourquoi ce test existe
-----------------------
``{# … #}`` de Django est **mono-ligne uniquement**. Un commentaire qui court
sur deux lignes n'est pas reconnu comme commentaire : il est rendu **tel quel
dans le HTML** et s'affiche à l'utilisateur. Le bug est silencieux (aucune
erreur, aucun test rouge) et n'apparaît qu'à l'écran.

La convention du projet est donc : **zéro `{# #}` dans les templates**. Les
explications vont dans le code Python, le CSS ou la doc — pas dans le rendu.
Ce test verrouille la convention pour tout le monde, y compris les agents.
"""
from pathlib import Path

import pytest

TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "templates"


def _templates():
    return sorted(TEMPLATES_DIR.rglob("*.html"))


def test_templates_directory_is_found():
    assert TEMPLATES_DIR.is_dir(), TEMPLATES_DIR
    assert _templates(), "aucun template trouvé — le chemin a dû bouger"


@pytest.mark.parametrize("path", _templates(), ids=lambda p: p.name)
def test_no_django_comment_markup(path):
    """Aucun `{#` : le mono-ligne est toléré par Django, le multi-ligne fuit.

    On interdit les deux plutôt que d'espérer que personne n'écrira jamais un
    commentaire sur deux lignes.
    """
    text = path.read_text(encoding="utf-8")
    assert "{#" not in text, (
        f"{path.relative_to(TEMPLATES_DIR)} contient un commentaire de template. "
        "Un `{# … #}` sur plusieurs lignes s'affiche dans la page. "
        "Mettre l'explication dans le code Python/CSS."
    )


def test_multiline_comment_would_leak_to_html():
    """Documente le comportement de Django qui justifie la règle ci-dessus."""
    from django.template import Context, Template

    assert Template("{# une ligne #}X").render(Context({})) == "X"
    rendered = Template("{# ligne un\nligne deux #}X").render(Context({}))
    assert "ligne un" in rendered  # le commentaire multi-ligne FUIT
