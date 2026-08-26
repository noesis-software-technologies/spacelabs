from django.contrib import admin

from .models import Assignment, Mission, Task


class TaskInline(admin.TabularInline):
    model = Task
    extra = 0


@admin.register(Mission)
class MissionAdmin(admin.ModelAdmin):
    list_display = ("goal", "workspace", "status", "mode", "max_parallel")
    list_filter = ("status", "mode")
    inlines = [TaskInline]


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("task", "pane", "started_at", "ended_at", "outcome")
