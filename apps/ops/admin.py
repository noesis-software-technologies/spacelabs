from django.contrib import admin

from .models import MCPAlert, RuntimeHeartbeat, UsageSnapshot


@admin.register(UsageSnapshot)
class UsageSnapshotAdmin(admin.ModelAdmin):
    list_display = ["owner", "taken_at", "active_panes", "max_panes", "cost_usd_today", "turns_today"]
    list_filter = ["owner"]


@admin.register(RuntimeHeartbeat)
class RuntimeHeartbeatAdmin(admin.ModelAdmin):
    list_display = ["boot_id", "last_seen"]


@admin.register(MCPAlert)
class MCPAlertAdmin(admin.ModelAdmin):
    list_display = ["pane", "detail", "resolved", "created_at"]
    list_filter = ["resolved"]
