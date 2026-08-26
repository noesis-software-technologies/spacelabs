from django.contrib import admin

from .models import ObserverSettings, RedactionRule


@admin.register(RedactionRule)
class RedactionRuleAdmin(admin.ModelAdmin):
    list_display = ["pattern", "replacement", "is_regex", "is_active", "owner"]


@admin.register(ObserverSettings)
class ObserverSettingsAdmin(admin.ModelAdmin):
    list_display = ["owner", "live"]
