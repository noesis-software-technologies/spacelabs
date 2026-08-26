"""S14 — la charte de marque est verrouillée par des tests.

Une charte qu'aucun test ne défend redevient une suggestion au bout de deux
sprints. Chaque règle de BRAND.md qui peut être vérifiée mécaniquement l'est
ici, avec le § correspondant en commentaire.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CSS_DIR = ROOT / "static" / "css"
TEMPLATES = ROOT / "templates"

DESIGN_SYSTEM = CSS_DIR / "design-system.css"
SURFACE_SHEETS = [CSS_DIR / n for n in ("terminal.css", "observer.css", "tasker.css")]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ── §3 Couleur ────────────────────────────────────────────────────────────────
def test_accent_is_spacelabs_orange():
    assert "--ds-accent: 26 93% 53%" in _read(DESIGN_SYSTEM)


def test_v1_hugging_face_yellow_is_gone():
    assert "48 100% 56%" not in _read(DESIGN_SYSTEM)


def test_background_is_the_deep_blue_black():
    assert "--ds-bg: 240 11% 4%" in _read(DESIGN_SYSTEM)


def test_v1_warm_anthracite_is_gone():
    assert "45 8% 8%" not in _read(DESIGN_SYSTEM)


def test_warn_is_not_the_same_colour_as_the_accent():
    """Bug de la v1 : un pane « attend une entrée » était indiscernable d'un
    bouton de marque."""
    css = _read(DESIGN_SYSTEM)
    warn = re.search(r"--ds-warn:\s*([^;]+);", css).group(1).strip()
    accent2 = re.search(r"--ds-accent-2:\s*([^;]+);", css).group(1).strip()
    accent = re.search(r"--ds-accent:\s*([^;]+);", css).group(1).strip()
    assert warn not in (accent, accent2)


def test_voice_blue_exists_and_differs_from_danger():
    """§3 : « j'écoute » n'est pas une panne."""
    css = _read(DESIGN_SYSTEM)
    voice = re.search(r"--ds-voice:\s*([^;]+);", css).group(1).strip()
    danger = re.search(r"--ds-danger:\s*([^;]+);", css).group(1).strip()
    assert voice and voice != danger


def test_every_agent_runtime_has_its_own_colour():
    css = _read(DESIGN_SYSTEM)
    tokens = re.findall(r"--ds-agent-(\w+):\s*([^;]+);", css)
    names = {n for n, _ in tokens}
    assert names == {"claude", "codex", "cursor", "gemini", "opencode"}
    values = [v.strip() for _, v in tokens]
    assert len(set(values)) == len(values), "deux runtimes partagent une teinte"


# ── §2 Typographie ────────────────────────────────────────────────────────────
def test_display_font_replaces_the_v1_serif():
    css = _read(DESIGN_SYSTEM)
    assert "--ds-font-display:" in css
    assert "--ds-display-tracking:" in css


@pytest.mark.parametrize("sheet", [DESIGN_SYSTEM] + SURFACE_SHEETS, ids=lambda p: p.name)
def test_no_stylesheet_still_uses_the_serif(sheet):
    """§2 : la réintroduire demande de modifier BRAND.md d'abord."""
    assert "var(--ds-font-serif)" not in _read(sheet)


# ── §10 Application ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("sheet", SURFACE_SHEETS, ids=lambda p: p.name)
def test_surface_sheets_hold_no_hardcoded_colour(sheet):
    """Rethémer = éditer les :root du design system, rien d'autre."""
    css = _read(sheet)
    hexes = [h for h in re.findall(r"#[0-9a-fA-F]{3,8}\b", css) if h.lower() not in ("#fff", "#000")]
    assert not hexes, f"{sheet.name} : couleurs en dur {hexes[:5]}"


@pytest.mark.parametrize("sheet", [DESIGN_SYSTEM] + SURFACE_SHEETS, ids=lambda p: p.name)
def test_every_ds_token_used_is_defined(sheet):
    defined = set(re.findall(r"(--ds-[\w-]+)\s*:", _read(DESIGN_SYSTEM)))
    local = set(re.findall(r"(--ds-[\w-]+)\s*:", _read(sheet)))
    used = set(re.findall(r"var\((--ds-[\w-]+)", _read(sheet)))
    missing = sorted(used - defined - local)
    assert not missing, f"{sheet.name} : tokens non définis {missing}"


# ── §6 Mouvement ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("sheet", [DESIGN_SYSTEM] + SURFACE_SHEETS, ids=lambda p: p.name)
def test_continuous_motion_has_a_reduced_motion_variant(sheet):
    css = _read(sheet)
    if "@keyframes" not in css:
        return
    assert "prefers-reduced-motion" in css, f"{sheet.name} anime sans variante réduite"


# ── §1 et §7 Nom et ton ───────────────────────────────────────────────────────
def _visible_templates():
    return sorted(TEMPLATES.rglob("*.html"))


@pytest.mark.parametrize("path", _visible_templates(), ids=lambda p: p.name)
def test_no_v1_product_name_is_shown_to_the_user(path):
    """§9 : le produit s'appelle SpaceLabs, pas « le cockpit »."""
    text = _read(path)
    # Les URL internes (/cockpit/, {% url %}) restent : c'est de la plomberie.
    visible = re.sub(r"\{%.*?%\}", "", text, flags=re.S)
    visible = re.sub(r'href="/cockpit/[^"]*"', "", visible)
    visible = re.sub(r"<!--.*?-->", "", visible, flags=re.S)
    for bad in ("cockpeet", "OpenCockpeet"):
        assert bad.lower() not in visible.lower(), f"{path.name} montre « {bad} »"
    assert "cockpit" not in visible.lower(), f"{path.name} montre encore « cockpit »"


@pytest.mark.parametrize("path", _visible_templates(), ids=lambda p: p.name)
def test_product_name_is_spelled_correctly(path):
    """§7 : SpaceLabs, un mot, deux capitales."""
    text = _read(path)
    for wrong in ("Spacelabs", "Space Labs", "spaceLabs"):
        assert wrong not in text, f"{path.name} écrit « {wrong} »"


@pytest.mark.parametrize("path", _visible_templates(), ids=lambda p: p.name)
def test_no_emoji_in_the_interface(path):
    """§1 : ton direct, sans esbroufe."""
    text = _read(path)
    emoji = re.findall(r"[\U0001F300-\U0001FAFF\U00002700-\U000027BF]", text)
    assert not emoji, f"{path.name} contient des emoji {emoji[:3]}"


# ── §4 Densité ────────────────────────────────────────────────────────────────
def test_the_four_density_tiers_exist():
    css = _read(DESIGN_SYSTEM)
    for tier in ("cozy", "compact", "dense", "micro"):
        assert f'[data-density="{tier}"]' in css


def test_pane_font_size_is_never_hardcoded():
    """§4 : la densité ne tiendrait pas si une feuille figeait la taille."""
    css = _read(CSS_DIR / "terminal.css")
    body = re.search(r"\.pane-body\s*\{[^}]*\}", css).group(0)
    assert "var(--ds-pane-fs)" in body


# ── La charte elle-même ───────────────────────────────────────────────────────
def test_brand_document_exists_and_covers_its_sections():
    brand = _read(ROOT / "BRAND.md")
    for section in ("Typographie", "Couleur", "Densité", "Mouvement", "marque"):
        assert section in brand
