"""AUTH_USER_MODEL custom dès le commit initial (Blueprint §2.1)."""
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Mono-user en v1 locale ; l'axe [TENANCY]=par user est acté dès J0 :
    tout objet métier (Workspace, Pane — Sprint 2) portera un FK owner filtré."""
