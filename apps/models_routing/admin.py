from django.contrib import admin

from .models import MissionTokenBudget, ModelBackend, RoutingRule, RunLog


@admin.register(ModelBackend)
class ModelBackendAdmin(admin.ModelAdmin):
    list_display = ("slug", "kind", "model_id", "enabled", "healthy", "last_health_at")
    list_filter = ("kind", "enabled", "healthy")


@admin.register(RoutingRule)
class RoutingRuleAdmin(admin.ModelAdmin):
    list_display = ("order", "task_class", "max_est_tokens", "backend", "enabled")
    list_editable = ("enabled",)
    ordering = ("order",)


@admin.register(MissionTokenBudget)
class MissionTokenBudgetAdmin(admin.ModelAdmin):
    list_display = ("mission", "budget_tokens", "spent_prompt", "spent_completion", "policy_on_exhaust")


@admin.register(RunLog)
class RunLogAdmin(admin.ModelAdmin):
    list_display = ("id", "backend", "task_class", "status", "started_at", "prompt_tokens", "completion_tokens", "duration_ms")
    list_filter = ("status", "backend", "task_class")
    readonly_fields = [f.name for f in RunLog._meta.fields]
