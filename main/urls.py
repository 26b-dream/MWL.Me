# Django
from django.urls import path

# Local
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("recommendations", views.recommendations, name="recommendations"),
    path("json_response", views.json_response, name="json_response"),
    path("update/<str:username>", views.update, name="update"),
    path("delete/<str:username>", views.delete, name="delete"),
]
