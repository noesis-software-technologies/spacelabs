from django.urls import path

from . import views

app_name = "vinted"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("commandes/<int:pk>/expedier/", views.order_ship, name="order_ship"),
    path("commandes/<int:pk>/livre/", views.order_delivered, name="order_delivered"),
    path("commandes/<int:pk>/suivi/", views.order_tracking, name="order_tracking"),
    path("commandes/<int:pk>/update/", views.order_update, name="order_update"),
    path("entrepot/", views.entrepot, name="entrepot"),
    path("entrepot/ajouter/", views.stock_add, name="stock_add"),
    path("entrepot/<int:pk>/update/", views.stock_update, name="stock_update"),
]
