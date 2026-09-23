from django.contrib import admin

from .models import VintedListing, VintedOrder


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
                    "transporteur", "tracking", "date_vente")
    list_filter = ("plateforme", "statut_envoi", "transporteur", "date_vente")
    search_fields = ("numero", "titre", "acheteur", "tracking", "notes")
    list_editable = ("statut_envoi", "transporteur", "tracking")
    date_hierarchy = "date_vente"
    autocomplete_fields = ("listing",)
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
