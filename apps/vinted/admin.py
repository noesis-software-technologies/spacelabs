from django.contrib import admin
from django.utils.html import format_html

from .models import Fournisseur, StockItem, VintedListing, VintedOrder


@admin.register(Fournisseur)
class FournisseurAdmin(admin.ModelAdmin):
    list_display = ("nom", "canal", "contact", "actif")
    list_filter = ("actif", "canal")
    search_fields = ("nom", "canal", "contact", "notes")


@admin.register(VintedListing)
class VintedListingAdmin(admin.ModelAdmin):
    list_display = ("id", "ref", "titre", "prix", "etat", "format_colis",
                    "statut", "cree_le")
    list_filter = ("statut", "etat", "marque")
    search_fields = ("ref", "titre", "description", "vinted_url")
    readonly_fields = ("cree_le", "maj_le")


@admin.register(VintedOrder)
class VintedOrderAdmin(admin.ModelAdmin):
    list_display = ("numero", "plateforme", "titre", "acheteur", "prix_achat",
                    "prix_vente", "benefice_col", "marge_col", "statut_envoi",
                    "transporteur", "tracking", "suivi_col", "date_vente")
    list_filter = ("plateforme", "fournisseur", "statut_envoi", "transporteur", "date_vente")
    search_fields = ("numero", "titre", "acheteur", "tracking", "notes")
    list_editable = ("statut_envoi", "transporteur", "tracking")
    date_hierarchy = "date_vente"
    autocomplete_fields = ("listing", "fournisseur")
    readonly_fields = ("benefice_col", "marge_col", "cree_le", "maj_le")
    fieldsets = (
        ("Article", {"fields": ("plateforme", "listing", "titre", "numero", "acheteur")}),
        ("Achat / vente / bénéfice", {
            "fields": ("prix_achat", "prix_vente", "frais", "benefice_col", "marge_col")}),
        ("Envoi", {
            "fields": ("statut_envoi", "transporteur", "tracking",
                       "date_vente", "date_expedition", "date_livraison")}),
        ("Divers", {"fields": ("notes", "cree_le", "maj_le")}),
    )

    @admin.display(description="Bénéfice")
    def benefice_col(self, obj):
        return f"{obj.benefice:.2f} €"

    @admin.display(description="Marge")
    def marge_col(self, obj):
        return "—" if obj.marge_pct is None else f"{obj.marge_pct} %"

    @admin.display(description="Suivi")
    def suivi_col(self, obj):
        if obj.tracking_url:
            return format_html('<a href="{}" target="_blank" rel="noopener">{} ↗</a>',
                               obj.tracking_url, obj.tracking)
        return obj.tracking or "—"


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = ("nom", "reference", "fournisseur", "source", "prix_achat",
                    "quantite", "destin", "statut", "gradeur", "date_reception")
    list_filter = ("statut", "destin", "fournisseur", "source")
    search_fields = ("nom", "reference", "notes", "gradeur")
    list_editable = ("destin", "statut")
    autocomplete_fields = ("fournisseur",)
    date_hierarchy = "date_achat"
    readonly_fields = ("cree_le", "maj_le")
