from django.contrib import admin

from .models import MarketListing


@admin.register(MarketListing)
class MarketListingAdmin(admin.ModelAdmin):
    list_display = ("id", "plateforme", "listing_type", "titre", "prix",
                    "prix_reserve", "statut", "external_id", "cree_le")
    list_filter = ("plateforme", "listing_type", "statut")
    search_fields = ("titre", "external_id", "catalog_id", "message")
    autocomplete_fields = ("source_listing",)
    readonly_fields = ("cree_le", "maj_le")
    list_editable = ("statut",)
