"""Forms Django systématiques (Blueprint §2.3) — jamais de request.POST brut."""
import os

from django import forms
from django.conf import settings

from .models import HeadlessPane, PtyPane, Workspace


class WorkspaceForm(forms.ModelForm):
    class Meta:
        model = Workspace
        fields = ["name", "cwd", "max_panes"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "ds-input", "autofocus": True}),
            "cwd": forms.TextInput(attrs={"class": "ds-input", "placeholder": "~/mes-projets/app"}),
            # Le réglage « n instances » du produit, par workspace.
            "max_panes": forms.NumberInput(
                attrs={"class": "ds-input", "min": 1, "max": 64,
                       "placeholder": f"défaut : {settings.COCKPIT_MAX_PANES}"}
            ),
        }

    def clean_max_panes(self):
        value = self.cleaned_data.get("max_panes")
        if value in (None, ""):
            return None          # vide = plafond global, pas zéro
        if value < 1:
            raise forms.ValidationError("Au moins un agent, sinon le workspace est inutilisable.")
        return value

    def clean_cwd(self):
        cwd = self.cleaned_data["cwd"].strip() or "~"
        expanded = os.path.expanduser(cwd)
        if not os.path.isdir(expanded):
            raise forms.ValidationError("Ce répertoire n'existe pas sur la machine hôte.")
        return cwd


class PtyPaneForm(forms.ModelForm):
    class Meta:
        model = PtyPane
        fields = ["title", "cmd", "cwd", "public_alias"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "ds-input", "placeholder": "auto"}),
            "cmd": forms.TextInput(attrs={"class": "ds-input"}),
            "cwd": forms.TextInput(attrs={"class": "ds-input", "placeholder": "hérité du workspace"}),
            "public_alias": forms.TextInput(attrs={"class": "ds-input", "placeholder": "nom affiché aux spectateurs"}),
        }

    def clean_cmd(self):
        """Même règle que le manager, importée — jamais recopiée."""
        from apps.runtime.services.pane_manager import (
            CommandNotAllowed,
            resolve_allowed_binary,
        )

        cmd = self.cleaned_data["cmd"].strip()
        parts = cmd.split()
        try:
            resolve_allowed_binary(parts[0] if parts else "")
        except CommandNotAllowed as exc:
            raise forms.ValidationError(str(exc)) from exc
        return cmd

    def clean_cwd(self):
        cwd = self.cleaned_data["cwd"].strip()
        if cwd and not os.path.isdir(os.path.expanduser(cwd)):
            raise forms.ValidationError("Ce répertoire n'existe pas sur la machine hôte.")
        return cwd


class HeadlessPaneForm(forms.ModelForm):
    class Meta:
        model = HeadlessPane
        fields = ["title", "prompt_initial"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "ds-input", "placeholder": "auto"}),
            "prompt_initial": forms.Textarea(attrs={"class": "ds-input", "rows": 3}),
        }


def form_for_kind(kind):
    """Résolution via le registre (source unique dans models)."""
    from .models import form_for

    return form_for(kind)
