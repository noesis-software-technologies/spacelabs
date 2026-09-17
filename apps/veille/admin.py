from django.contrib import admin

from .models import Blog, PressItem


@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    list_display = ("nom", "domaine", "categorie", "is_principal", "statut")
    list_filter = ("statut", "is_principal")


@admin.register(PressItem)
class PressItemAdmin(admin.ModelAdmin):
    list_display = ("recu_le", "categorie", "sujet", "blog_cible",
                    "draft_statut", "publier_le", "statut")
    list_filter = ("categorie", "draft_statut", "statut", "blog_cible", "publier_le")
    search_fields = ("sujet", "expediteur", "corps", "draft_titre", "draft_corps")
    list_editable = ("draft_statut", "publier_le", "blog_cible")
    date_hierarchy = "recu_le"
    readonly_fields = ("draft_genere_le", "cree_le")
    fieldsets = (
        ("Communiqué", {
            "fields": ("message_id", "expediteur", "sujet", "recu_le",
                       "categorie", "blog_cible", "statut", "resume", "corps"),
        }),
        ("Brouillon (plume de Thérèse)", {
            "fields": ("draft_statut", "publier_le", "draft_genere_le",
                       "draft_titre", "draft_chapo", "draft_corps"),
        }),
    )
