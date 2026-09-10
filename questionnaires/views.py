from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .models import QuestionnaireVersion


@login_required
def fill_page(request, version_id):
    """家長端填答頁的外殼。實際的題目呈現與分支邏輯在前端 Vue 元件，
    schema 由 /api/questionnaires/<id>/schema/ 載入。

    ?preview=1 ：預覽模式，允許看草稿、不寫入任何填答（正式文件（三））。
    ?child=<id>：指定填答對象；正式介接後改由登入身分推導。
    """
    preview = request.GET.get("preview") == "1"

    version_qs = QuestionnaireVersion.objects.select_related("questionnaire")
    if not preview:
        version_qs = version_qs.filter(status=QuestionnaireVersion.Status.PUBLISHED)
    version = get_object_or_404(version_qs, pk=version_id)

    return render(request, "questionnaires/fill.html", {
        "version": version,
        "preview": preview,
        "child_id": request.GET.get("child", ""),
    })
