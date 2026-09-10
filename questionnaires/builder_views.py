"""問卷編輯器的 HTML 外殼頁（實際互動在 Vue）。"""

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render

from .models import Category, QuestionnaireVersion, Tier


@staff_member_required
def questionnaire_list_page(request):
    return render(request, "questionnaires/builder_list.html", {
        "categories": Category.objects.filter(is_active=True).order_by("order"),
        "tiers": Tier.objects.filter(is_active=True).order_by("order"),
    })


@staff_member_required
def editor_page(request, version_id):
    version = get_object_or_404(
        QuestionnaireVersion.objects.select_related("questionnaire"), pk=version_id
    )
    return render(request, "questionnaires/builder_editor.html", {
        "version": version,
    })
