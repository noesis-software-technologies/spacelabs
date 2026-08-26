"""Lecture de fichiers pour l'Éditeur — la partie dangereuse du sprint.

Cette surface expose le **vrai disque de l'utilisateur** dans un navigateur.
Tout est donc écrit en refusant par défaut. Quatre gardes, dans cet ordre :

1. **Confinement** : le chemin résolu (``resolve()``, donc liens symboliques
   suivis) doit rester sous la racine du workspace. C'est ce qui bloque
   ``../../.ssh`` *et* un lien symbolique qui pointe dehors.
2. **Secrets** : ``.env`` et consorts ne sont jamais listés ni lus. Le projet
   est utilisé en direct (streams) — un ``.env`` affiché est un secret publié.
   C'est un invariant du dépôt, pas une préférence.
3. **Taille** : plafond de lecture. Un fichier de 2 Go ne doit pas tuer le
   serveur parce qu'un utilisateur a cliqué dessus.
4. **Binaire** : on ne renvoie que du texte. Un binaire décodé en UTF-8 produit
   du bruit, au mieux.

Tout est **pur** (chemins et octets, pas de Django) : la sécurité se teste sans
base ni HTTP.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

MAX_BYTES = 512_000          # au-delà, on tronque plutôt que de charger
MAX_ENTRIES = 400            # un dossier de 50 000 fichiers ne bloque pas l'UI

# Jamais listés, jamais lus. Comparé sur le nom en minuscules.
SECRET_NAMES = {
    ".env", ".env.local", ".env.production", ".env.prod", ".env.dev",
    ".env.development", ".env.test", ".envrc", ".netrc", ".pgpass",
    "id_rsa", "id_ed25519", "credentials", "secrets.json", ".htpasswd",
}
SECRET_PREFIXES = (".env",)   # .env.n-importe-quoi
SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".keystore")

# Dossiers sans intérêt qui noient l'arborescence.
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "dist", "build", ".next", ".tox",
}

# Dossiers de secrets. Découvert en test réel : un workspace dont le cwd est
# « ~ » (le cas par défaut !) exposait ~/.ssh. Les CLÉS étaient bien bloquées
# par is_secret(), mais pas ~/.ssh/config ni known_hosts — qui décrivent toute
# l'infrastructure de l'utilisateur. On refuse le dossier entier.
SECRET_DIRS = {
    ".ssh", ".gnupg", ".aws", ".azure", ".kube", ".docker", ".config/gcloud",
    ".password-store", ".gem", ".npmrc.d", ".cargo/credentials",
}

TEXT_SUFFIXES = {
    ".md", ".txt", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yml", ".yaml",
    ".toml", ".cfg", ".ini", ".html", ".css", ".scss", ".sql", ".sh", ".rs",
    ".go", ".rb", ".java", ".c", ".h", ".cpp", ".xml", ".csv", ".gitignore",
    ".dockerfile", ".env.example",
}


class FileAccessError(Exception):
    """Accès refusé ou impossible. Le message est montré à l'utilisateur."""


@dataclass(frozen=True)
class Entry:
    name: str
    path: str          # relatif à la racine, c'est ce que l'UI manipule
    is_dir: bool
    size: int = 0

    @property
    def kind(self) -> str:
        if self.is_dir:
            return "folder"
        suffix = Path(self.name).suffix.lower()
        if suffix == ".md":
            return "md"
        if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif"}:
            return "img"
        return "file"


def is_secret_dir(name: str) -> bool:
    """Un dossier de secrets n'est ni listé ni traversé."""
    return name.lower() in SECRET_DIRS


def is_secret(name: str) -> bool:
    """Un fichier de secrets ne doit jamais apparaître, même dans la liste.

    Masquer seulement le contenu ne suffit pas : le seul NOM d'un fichier
    (``.env.production``) renseigne déjà un attaquant, et sa présence dans une
    capture de stream est une fuite.
    """
    low = name.lower()
    if low in SECRET_NAMES:
        return False if low == ".env.example" else True
    if low == ".env.example":
        return False
    if any(low.startswith(p) for p in SECRET_PREFIXES):
        return True
    return any(low.endswith(s) for s in SECRET_SUFFIXES)


def workspace_root(workspace) -> Path:
    raw = (workspace.cwd or "").strip() or "~"
    root = Path(raw).expanduser()
    try:
        return root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise FileAccessError(f"Répertoire du workspace introuvable : {raw}") from exc


def safe_join(root: Path, relative: str) -> Path:
    """Résout ``relative`` sous ``root``, ou lève.

    ``resolve()`` suit les liens symboliques AVANT la comparaison : un lien
    ``notes -> /etc`` échoue ici, alors qu'une simple vérification textuelle du
    préfixe l'aurait laissé passer.
    """
    relative = (relative or "").strip().lstrip("/")
    if "\x00" in relative:
        raise FileAccessError("Chemin invalide.")
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise FileAccessError("Chemin hors du workspace.")
    for part in Path(relative).parts:
        if is_secret(part) or is_secret_dir(part):
            raise FileAccessError("Ce fichier contient des secrets : lecture refusée.")
    return candidate


def list_dir(workspace, relative: str = "") -> list[Entry]:
    """Liste un dossier : dossiers d'abord, puis fichiers, alphabétiquement."""
    root = workspace_root(workspace)
    target = safe_join(root, relative)
    if not target.is_dir():
        raise FileAccessError("Ce n'est pas un dossier.")

    entries: list[Entry] = []
    try:
        children = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError as exc:
        raise FileAccessError("Lecture refusée par le système.") from exc

    for child in children[:MAX_ENTRIES]:
        if is_secret(child.name):
            continue
        if child.is_dir() and (child.name in SKIP_DIRS or is_secret_dir(child.name)):
            continue
        try:
            size = child.stat().st_size if child.is_file() else 0
        except OSError:
            size = 0
        entries.append(Entry(
            name=child.name,
            path=str(child.relative_to(root)),
            is_dir=child.is_dir(),
            size=size,
        ))
    return entries


def read_text(workspace, relative: str) -> tuple[str, bool]:
    """Renvoie ``(contenu, tronqué)``. Lève sur binaire, secret ou hors racine."""
    root = workspace_root(workspace)
    target = safe_join(root, relative)
    if not target.is_file():
        raise FileAccessError("Fichier introuvable.")

    try:
        raw = target.read_bytes()[: MAX_BYTES + 1]
    except (OSError, PermissionError) as exc:
        raise FileAccessError("Lecture impossible.") from exc

    truncated = len(raw) > MAX_BYTES
    raw = raw[:MAX_BYTES]
    if b"\x00" in raw:
        raise FileAccessError("Fichier binaire : pas d'aperçu.")
    try:
        return raw.decode("utf-8"), truncated
    except UnicodeDecodeError:
        raise FileAccessError("Fichier non lisible en UTF-8.") from None
