from django.urls import path

from . import views

app_name = "vinted"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("commandes/<int:pk>/expedier/", views.order_ship, name="order_ship"),
    path("commandes/<int:pk>/livre/", views.order_delivered, name="order_delivered"),
]
