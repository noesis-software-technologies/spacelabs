from django.urls import path

from . import views

app_name = "workspaces"

urlpatterns = [
    path("", views.home, name="home"),
    path("nouveau/", views.create, name="create"),
    path("sidebar/", views.sidebar, name="sidebar"),
    path("<slug:slug>/fichiers/", views.explorer, name="explorer"),
    path("<slug:slug>/fichier/", views.file_view, name="file"),
    path("<slug:slug>/", views.detail, name="detail"),
    path("<slug:slug>/renommer/", views.update, name="update"),
    path("<slug:slug>/supprimer/", views.delete, name="delete"),
    path("<slug:slug>/agents/", views.agent_picker, name="agent_picker"),
    path("<slug:slug>/panes/<str:kind>/nouveau/", views.pane_create, name="pane_create"),
    path("<slug:slug>/panes/<int:pane_id>/supprimer/", views.pane_delete, name="pane_delete"),
]
