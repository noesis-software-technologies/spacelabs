from django.contrib import admin

from .models import EventLog


@admin.register(EventLog)
class EventLogAdmin(admin.ModelAdmin):
    list_display = ["pane", "seq", "origin", "event_type", "created_at"]
    list_filter = ["origin", "event_type"]
