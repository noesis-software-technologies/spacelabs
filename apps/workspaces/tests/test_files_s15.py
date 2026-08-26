"""S15 — sécurité de l'Éditeur. La partie qui compte.

Cette surface expose le disque de l'utilisateur dans un navigateur. Chaque test
correspond à une attaque ou à un accident précis. S'il en manque un, c'est une
faille, pas une fonctionnalité absente.
"""
import os

import pytest
from django.contrib.auth import get_user_model

from apps.workspaces.models import Workspace
from apps.workspaces.services.files import (
    FileAccessError,
    Entry,
    is_secret,
    list_dir,
    read_text,
    safe_join,
    workspace_root,
)

User = get_user_model()


@pytest.fixture
def tree(tmp_path):
    """Un workspace réaliste, avec un secret et un piège."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('salut')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Projet\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET_KEY=tres-secret\n", encoding="utf-8")
    (tmp_path / ".env.production").write_text("STRIPE=live_xxx\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("SECRET_KEY=\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "binaire.bin").write_bytes(b"\x00\x01\x02rien de lisible")
    return tmp_path


@pytest.fixture
def workspace(db, tree):
    u = User.objects.create_user(username="pilote", password="x")
    return Workspace.objects.create(owner=u, name="W", cwd=str(tree))


# ── Confinement ───────────────────────────────────────────────────────────────
@pytest.mark.django_db
@pytest.mark.parametrize(
    "attack",
    ["../", "../../", "../../../etc/passwd", "src/../../etc/passwd",
     "/etc/passwd", "....//....//etc/passwd", "src/../../../root",
     "..", "src/..%2f..", "./../.."],
)
def test_traversal_never_escapes_the_root(workspace, attack):
    """La propriété qui compte n'est pas « ça lève », c'est « ça ne sort pas ».

    Certaines entrées sont neutralisées sans erreur : « /etc/passwd » devient
    « <racine>/etc/passwd » (le slash de tête est retiré), et « .... » est un
    nom de dossier littéral, pas une remontée. Les deux restent DANS la racine —
    c'est correct. On vérifie donc le confinement, pas le message.
    """
    root = workspace_root(workspace)
    try:
        resolved = safe_join(root, attack)
    except FileAccessError:
        return          # refus explicite : très bien aussi
    assert resolved == root or root in resolved.parents, f"{attack} est sorti : {resolved}"


@pytest.mark.django_db
def test_symlink_pointing_outside_is_refused(workspace, tree, tmp_path_factory):
    """Le piège que la comparaison de préfixe textuel laisse passer."""
    outside = tmp_path_factory.mktemp("dehors")
    (outside / "vole.txt").write_text("données volées", encoding="utf-8")
    link = tree / "raccourci"
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError):
        pytest.skip("liens symboliques indisponibles")

    with pytest.raises(FileAccessError, match="hors du workspace"):
        read_text(workspace, "raccourci/vole.txt")


@pytest.mark.django_db
def test_null_byte_is_refused(workspace):
    with pytest.raises(FileAccessError):
        safe_join(workspace_root(workspace), "src/main\x00.py")


@pytest.mark.django_db
def test_legitimate_paths_still_work(workspace):
    assert read_text(workspace, "README.md")[0].startswith("# Projet")
    assert read_text(workspace, "src/main.py")[0].startswith("print")
    assert any(e.name == "main.py" for e in list_dir(workspace, "src"))


# ── Secrets ───────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "name", [".env", ".env.local", ".env.production", ".env.n-importe-quoi",
             "id_rsa", "cle.pem", "serveur.key", ".netrc", ".pgpass"],
)
def test_secret_files_are_recognised(name):
    assert is_secret(name) is True


@pytest.mark.parametrize("name", [".env.example", "README.md", "main.py", "envoi.py"])
def test_ordinary_files_are_not_flagged(name):
    assert is_secret(name) is False


@pytest.mark.django_db
def test_secrets_never_appear_in_a_listing(workspace):
    """Le NOM seul d'un .env.production renseigne déjà un attaquant — et le
    projet est utilisé en direct."""
    names = {e.name for e in list_dir(workspace)}
    assert ".env" not in names
    assert ".env.production" not in names
    assert ".env.example" in names, "l'exemple, lui, doit rester visible"


@pytest.mark.django_db
def test_reading_a_secret_is_refused(workspace):
    for path in (".env", ".env.production"):
        with pytest.raises(FileAccessError, match="secrets"):
            read_text(workspace, path)


@pytest.mark.django_db
def test_secret_in_a_subdirectory_is_refused(workspace, tree):
    (tree / "src" / ".env").write_text("X=1", encoding="utf-8")
    with pytest.raises(FileAccessError, match="secrets"):
        read_text(workspace, "src/.env")


# ── Robustesse ────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_binary_files_are_refused(workspace):
    with pytest.raises(FileAccessError, match="binaire"):
        read_text(workspace, "binaire.bin")


@pytest.mark.django_db
def test_huge_files_are_truncated_not_loaded(workspace, tree):
    (tree / "gros.log").write_text("x" * 900_000, encoding="utf-8")
    content, truncated = read_text(workspace, "gros.log")
    assert truncated is True
    assert len(content) <= 512_000


@pytest.mark.django_db
def test_noise_directories_are_hidden(workspace):
    assert "node_modules" not in {e.name for e in list_dir(workspace)}


@pytest.mark.django_db
def test_missing_file_is_a_clean_error(workspace):
    with pytest.raises(FileAccessError, match="introuvable"):
        read_text(workspace, "n-existe-pas.md")


@pytest.mark.django_db
def test_broken_workspace_root_is_reported(db):
    u = User.objects.create_user(username="x", password="x")
    ws = Workspace.objects.create(owner=u, name="W", cwd="/chemin/qui/n/existe/pas")
    with pytest.raises(FileAccessError, match="introuvable"):
        list_dir(ws)


def test_entry_kind_classifies_files():
    assert Entry("a.md", "a.md", False).kind == "md"
    assert Entry("a.png", "a.png", False).kind == "img"
    assert Entry("src", "src", True).kind == "folder"
    assert Entry("a.py", "a.py", False).kind == "file"


# ── Vues ──────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_explorer_view_lists_and_hides_secrets(client, workspace):
    client.force_login(workspace.owner)
    html = client.get(f"/cockpit/{workspace.slug}/fichiers/").content.decode()
    assert "README.md" in html
    assert ".env.production" not in html


@pytest.mark.django_db
def test_file_view_shows_an_error_instead_of_a_secret(client, workspace):
    client.force_login(workspace.owner)
    html = client.get(
        f"/cockpit/{workspace.slug}/fichier/", {"path": ".env"}
    ).content.decode()
    assert "tres-secret" not in html
    assert "secrets" in html


@pytest.mark.django_db
def test_explorer_refuses_someone_elses_workspace(client, workspace):
    other = User.objects.create_user(username="autre", password="x")
    client.force_login(other)
    assert client.get(f"/cockpit/{workspace.slug}/fichiers/").status_code == 404


# ── Trouvé sur serveur réel : cwd = ~ exposait ~/.ssh ─────────────────────────
@pytest.mark.django_db
def test_secret_directories_are_never_listed(workspace, tree):
    """Le workspace par défaut pointe sur « ~ ». Les clés étaient bloquées,
    mais pas ~/.ssh/config ni known_hosts, qui décrivent l'infra complète."""
    (tree / ".ssh").mkdir()
    (tree / ".ssh" / "config").write_text("Host prod\n  HostName 10.0.0.1\n", encoding="utf-8")
    (tree / ".aws").mkdir()

    names = {e.name for e in list_dir(workspace)}
    assert ".ssh" not in names
    assert ".aws" not in names


@pytest.mark.django_db
def test_reading_inside_a_secret_directory_is_refused(workspace, tree):
    (tree / ".ssh").mkdir()
    (tree / ".ssh" / "known_hosts").write_text("prod ssh-rsa AAAA", encoding="utf-8")
    with pytest.raises(FileAccessError, match="secrets"):
        read_text(workspace, ".ssh/known_hosts")
