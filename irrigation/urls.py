from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("api/sensor/", views.api_sensor_ingest, name="api_sensor_ingest"),
    path("api/state/", views.api_dashboard_state, name="api_dashboard_state"),
    path("api/control/", views.api_dashboard_control, name="api_dashboard_control"),
]
