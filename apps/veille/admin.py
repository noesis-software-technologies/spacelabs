from django.contrib import admin

from .models import Blog, PressItem


@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    list_display = ("nom", "domaine", "categorie", "is_principal", "statut")
    list_filter = ("statut", "is_principal")


@admin.register(PressItem)
class PressItemAdmin(admin.ModelAdmin):
    list_display = ("recu_le", "categorie", "sujet", "blog_cible", "statut")
    list_filter = ("categorie", "statut", "blog_cible")
    search_fields = ("sujet", "expediteur", "corps")
    list_editable = ("statut", "blog_cible")
    date_hierarchy = "recu_le"
