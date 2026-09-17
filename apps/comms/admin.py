from django.contrib import admin

from .models import Message


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("recu_le", "channel", "priorite", "needs_reply", "expediteur", "sujet", "statut")
    list_filter = ("channel", "priorite", "needs_reply", "statut", "categorie")
    search_fields = ("expediteur", "sujet", "corps")
    list_editable = ("statut",)
    date_hierarchy = "recu_le"
