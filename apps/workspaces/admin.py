from django.contrib import admin

from .models import HeadlessPane, PtyPane, Workspace


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "slug", "cwd"]
    list_select_related = ["owner"]


@admin.register(PtyPane)
class PtyPaneAdmin(admin.ModelAdmin):
    list_display = ["title", "workspace", "cmd", "status"]
    list_select_related = ["workspace"]


@admin.register(HeadlessPane)
class HeadlessPaneAdmin(admin.ModelAdmin):
    list_display = ["title", "workspace", "status"]
    list_select_related = ["workspace"]
