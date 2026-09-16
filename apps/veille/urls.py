from django.urls import path

from . import views

app_name = "veille"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
]
