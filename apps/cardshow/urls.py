from django.urls import path

from . import views

app_name = "cardshow"

urlpatterns = [
    path("calcul/", views.calcul, name="calcul"),
    path("calcul/apercu/", views.apercu, name="apercu"),
]
