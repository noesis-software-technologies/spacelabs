"""Skills — consignes réutilisables, glissables sur un agent.

Le mécanisme le plus rentable du produit : capitaliser les prompts qui
marchent. Une skill n'est ni un agent ni une tâche — c'est un **fragment de
consigne** qu'on envoie à un agent déjà en cours.

Pas d'exécution ici : appliquer une skill = ``registry[pane.kind].dispatch``
(capacité S9). Aucun ``if pane.kind ==``.
"""
from django.conf import settings
from django.db import models


class SkillQuerySet(models.QuerySet):
    def visible_for(self, user):
        """Les skills intégrées + celles de l'utilisateur."""
        return self.filter(models.Q(is_builtin=True) | models.Q(owner=user))


class Skill(models.Model):
    class Tag(models.TextChoices):
        SECURITY = "security", "sécurité"
        GROWTH = "growth", "croissance"
        WORKFLOW = "workflow", "workflow"
        MEMORY = "memory", "mémoire"
        KNOWLEDGE = "knowledge", "connaissance"
        DEPLOY = "deploy", "déploiement"

    name = models.CharField(max_length=80)
    description = models.CharField(max_length=300, blank=True)
    # Le texte réellement envoyé à l'agent. C'est la valeur de l'objet.
    body = models.TextField("consigne")
    tag = models.CharField(max_length=16, choices=Tag.choices, default=Tag.WORKFLOW)
    # Intégrée = fournie avec le produit, non modifiable par l'utilisateur.
    is_builtin = models.BooleanField(default=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.CASCADE, related_name="skills",
    )
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = SkillQuerySet.as_manager()

    class Meta:
        ordering = ["-is_builtin", "order", "name"]

    def __str__(self):
        return self.name
