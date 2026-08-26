import re

from django import forms

from .models import RedactionRule


class RedactionRuleForm(forms.ModelForm):
    class Meta:
        model = RedactionRule
        fields = ["pattern", "replacement", "is_regex"]
        widgets = {
            "pattern": forms.TextInput(attrs={"class": "ds-input", "placeholder": "chaîne ou regex à masquer", "autofocus": True}),
            "replacement": forms.TextInput(attrs={"class": "ds-input"}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("is_regex") and cleaned.get("pattern"):
            try:
                re.compile(cleaned["pattern"])
            except re.error as exc:
                self.add_error("pattern", f"Regex invalide : {exc}")
        return cleaned
