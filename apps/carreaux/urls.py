from django.urls import path

from . import api, views

app_name = "carreaux"

urlpatterns = [
    path("", views.catalogue, name="catalogue"),
    path("panier/", views.panier, name="panier"),
    path("panier/add/<int:product_id>/", views.panier_add, name="panier_add"),
    path("panier/remove/<int:product_id>/", views.panier_remove, name="panier_remove"),
    path("panier/vider/", views.panier_vider, name="panier_vider"),
    path("checkout/", views.checkout, name="checkout"),
    path("checkout/instant/<int:product_id>/", views.checkout_instant, name="checkout_instant"),
    path("success/", views.success, name="success"),
    path("cancel/", views.cancel, name="cancel"),
    path("webhook/", views.webhook, name="webhook"),
    path("<slug:slug>/", views.produit, name="produit"),
    # API sécurisée (Bearer token)
    path("api/inventory/", api.inventory, name="api_inventory"),
    path("api/inventory/<int:product_id>/", api.inventory_detail, name="api_inventory_detail"),
    path("api/sold/<int:stock_item_id>/", api.mark_sold, name="api_mark_sold"),
    path("api/activate/<int:product_id>/", api.activate_product, name="api_activate"),
    path("api/deactivate/<int:product_id>/", api.deactivate_product, name="api_deactivate"),
    path("api/orders/", api.orders, name="api_orders"),
]
