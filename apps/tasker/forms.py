"""Forms systématiques (Blueprint §2.3)."""
from django import forms

from .models import Mission, Task


class MissionForm(forms.ModelForm):
    class Meta:
        model = Mission
        fields = ["goal", "mode", "max_parallel", "budget_usd"]
        widgets = {
            "goal": forms.Textarea(attrs={"class": "ds-input", "rows": 3, "autofocus": True,
                                          "placeholder": "Ex. : ajouter des tests au module auth"}),
            "mode": forms.Select(attrs={"class": "ds-input"}),
            "max_parallel": forms.NumberInput(attrs={"class": "ds-input", "min": 1, "max": 16}),
            "budget_usd": forms.NumberInput(attrs={"class": "ds-input", "step": "0.5",
                                                   "placeholder": "vide = pas de plafond"}),
        }


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["key", "title", "brief", "order"]
        widgets = {
            "key": forms.TextInput(attrs={"class": "ds-input", "placeholder": "T1"}),
            "title": forms.TextInput(attrs={"class": "ds-input"}),
            "brief": forms.Textarea(attrs={"class": "ds-input", "rows": 2,
                                           "placeholder": "La consigne envoyée à l'agent"}),
            "order": forms.NumberInput(attrs={"class": "ds-input", "min": 0}),
        }
