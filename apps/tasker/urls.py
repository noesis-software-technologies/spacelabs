from django.urls import path

from . import views

app_name = "tasker"

urlpatterns = [
    path("w/<slug:slug>/", views.mission_list, name="missions"),
    path("w/<slug:slug>/nouvelle/", views.mission_create, name="mission_create"),
    path("<int:pk>/", views.mission, name="mission"),
    path("<int:pk>/swarm/", views.swarm, name="swarm"),
    path("<int:pk>/etat/", views.mission_state, name="mission_state"),
    path("<int:pk>/planifier/", views.mission_plan, name="mission_plan"),
    path("<int:pk>/supprimer/", views.mission_delete, name="mission_delete"),
    path("<int:pk>/taches/", views.task_create, name="task_create"),
    path("<int:pk>/taches/<int:task_id>/deplacer/", views.task_move, name="task_move"),
]
