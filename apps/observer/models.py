"""Confidentialité & diffusion — réglages de la « régie ».

Ligne produit (CDC §5) : PRIVÉ PAR DÉFAUT. La redaction est un filet,
pas une garantie — la règle affichée dans l'UI reste « confidentiel ⇒
pane privé ».
"""
from django.conf import settings
from django.db import models


class ObserverSettings(models.Model):
    """Mode live par opérateur. live=False ⇒ RIEN ne sort vers l'observateur."""

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="observer_settings"
    )
    live = models.BooleanField("mode live", default=False)

    class Meta:
        verbose_name = "réglages observateur"

    def __str__(self):
        return f"{self.owner} — live={self.live}"

    @classmethod
    def for_owner(cls, user):
        obj, _ = cls.objects.get_or_create(owner=user)
        return obj


class RedactionRule(models.Model):
    """Chaîne (ou regex) masquée côté SERVEUR avant toute diffusion publique."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="redaction_rules"
    )
    pattern = models.CharField("motif", max_length=200)
    replacement = models.CharField("remplacement", max_length=60, default="•••")
    is_regex = models.BooleanField("expression régulière", default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "règle de masquage"

    def __str__(self):
        return f"{self.pattern!r} → {self.replacement!r}"
