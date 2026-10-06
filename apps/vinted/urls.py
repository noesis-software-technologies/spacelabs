from django.urls import path

from . import views

app_name = "vinted"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("commandes/ajouter/", views.order_create, name="order_create"),
    path("commandes/<int:pk>/expedier/", views.order_ship, name="order_ship"),
    path("commandes/<int:pk>/livre/", views.order_delivered, name="order_delivered"),
    path("commandes/<int:pk>/suivi/", views.order_tracking, name="order_tracking"),
    path("commandes/<int:pk>/update/", views.order_update, name="order_update"),
    path("entrepot/", views.entrepot, name="entrepot"),
    path("entrepot/ajouter/", views.stock_add, name="stock_add"),
    path("entrepot/<int:pk>/update/", views.stock_update, name="stock_update"),
    path("lignes/<int:pk>/update/", views.line_update, name="line_update"),
    # Duesenberg — Telegram Mini-App
    path("duesenberg/", views.duesenberg, name="duesenberg"),
    path("duesenberg/api/", views.duesenberg_api, name="duesenberg_api"),
    # Simulateur de projection commerciale
    path("projection/", views.projection, name="projection"),
    path("projection/api/", views.projection_api, name="projection_api"),
    # Étiquettes prix — live show
    path("entrepot/<int:pk>/etiquette/", views.etiquette, name="etiquette"),
    path("entrepot/etiquettes/", views.etiquettes_lot, name="etiquettes_lot"),
    # Fiche publique carte — cible QR code client au card show
    path("carte/<int:pk>/", views.carte_publique, name="carte_publique"),
]
