from django.urls import path

from . import api_views, views

app_name = "questionnaires"

urlpatterns = [
    # 家長端
    path("", views.home, name="home"),
    path("child/<int:child_id>/", views.child_home, name="child-home"),
    path("fill/<int:version_id>/", views.fill_page, name="fill"),

    # JSON API（《開發規劃書》第六節）
    path("api/questionnaires/<int:version_id>/schema/",
         api_views.VersionSchemaView.as_view(), name="api-version-schema"),
    path("api/responses/",
         api_views.ResponseCreateView.as_view(), name="api-response-create"),
    path("api/responses/<int:response_id>/",
         api_views.ResponseDetailView.as_view(), name="api-response-detail"),
    path("api/responses/<int:response_id>/autosave/",
         api_views.ResponseAutosaveView.as_view(), name="api-response-autosave"),
    path("api/responses/<int:response_id>/complete/",
         api_views.ResponseCompleteView.as_view(), name="api-response-complete"),
]
