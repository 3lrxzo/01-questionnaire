"""M04 URL 設定。"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("questionnaires.urls")),
]
