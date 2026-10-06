from django.contrib import admin

from .models import BoutiqueOrder, BoutiqueOrderLine, BoutiqueProduct, BoutiqueReview


class OrderLineInline(admin.TabularInline):
    model = BoutiqueOrderLine
    extra = 0
    readonly_fields = ("product", "prix_unitaire", "quantite")


@admin.register(BoutiqueProduct)
class BoutiqueProductAdmin(admin.ModelAdmin):
    list_display = ("titre", "prix_vente", "actif", "cree_le")
    list_filter = ("actif",)
    search_fields = ("titre",)
    prepopulated_fields = {"slug": ("titre",)}


@admin.register(BoutiqueReview)
class BoutiqueReviewAdmin(admin.ModelAdmin):
    list_display = ("auteur", "note", "commentaire", "date")
    list_filter = ("note",)


@admin.register(BoutiqueOrder)
class BoutiqueOrderAdmin(admin.ModelAdmin):
    list_display = ("ref", "email", "total", "statut", "cree_le")
    list_filter = ("statut",)
    readonly_fields = ("ref", "stripe_session_id", "cree_le", "maj_le")
    inlines = [OrderLineInline]
