"""問卷編輯器的 URL（HTML 頁面 + staff API）。"""

from django.urls import path

from . import builder_api, builder_views

app_name = "builder"

urlpatterns = [
    # --- HTML 頁面 ---
    path("build/", builder_views.questionnaire_list_page, name="list"),
    path("build/version/<int:version_id>/", builder_views.editor_page, name="editor"),

    # --- API：問卷 / 版本 ---
    path("api/builder/questionnaires/",
         builder_api.QuestionnaireListCreateView.as_view(), name="api-questionnaires"),
    path("api/builder/versions/<int:version_id>/",
         builder_api.VersionBuilderView.as_view(), name="api-version"),
    path("api/builder/versions/<int:version_id>/publish/",
         builder_api.VersionPublishView.as_view(), name="api-version-publish"),
    path("api/builder/versions/<int:version_id>/clone/",
         builder_api.VersionCloneView.as_view(), name="api-version-clone"),
    path("api/builder/versions/<int:version_id>/retire/",
         builder_api.VersionRetireView.as_view(), name="api-version-retire"),
    path("api/builder/versions/<int:version_id>/reorder/",
         builder_api.ReorderView.as_view(), name="api-reorder"),

    # --- API：題組 ---
    path("api/builder/versions/<int:version_id>/sections/",
         builder_api.SectionCreateView.as_view(), name="api-section-create"),
    path("api/builder/sections/<int:section_id>/",
         builder_api.SectionDetailView.as_view(), name="api-section-detail"),

    # --- API：題目 ---
    path("api/builder/sections/<int:section_id>/questions/",
         builder_api.QuestionCreateView.as_view(), name="api-question-create"),
    path("api/builder/questions/<int:question_id>/",
         builder_api.QuestionDetailView.as_view(), name="api-question-detail"),

    # --- API：選項 ---
    path("api/builder/questions/<int:question_id>/options/",
         builder_api.OptionCreateView.as_view(), name="api-option-create"),
    path("api/builder/options/<int:option_id>/",
         builder_api.OptionDetailView.as_view(), name="api-option-detail"),

    # --- API：分支規則 ---
    path("api/builder/versions/<int:version_id>/branch-rules/",
         builder_api.BranchRuleCreateView.as_view(), name="api-rule-create"),
    path("api/builder/branch-rules/<int:rule_id>/",
         builder_api.BranchRuleDetailView.as_view(), name="api-rule-detail"),

    # --- API：適用規則 ---
    path("api/builder/versions/<int:version_id>/eligibility/",
         builder_api.EligibilityCreateView.as_view(), name="api-eligibility-create"),
    path("api/builder/eligibility/<int:rule_id>/",
         builder_api.EligibilityDetailView.as_view(), name="api-eligibility-detail"),
]
