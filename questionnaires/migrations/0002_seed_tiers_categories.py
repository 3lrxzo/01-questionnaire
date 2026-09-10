"""Tier 0～Tier 5 與基本分類的初始資料。

正式文件（四）：Tier 0～Tier 5 是第一階段的「最低支援基準」，不是上限。
用資料migration 建立這六筆，是為了三台開發機 migrate 後就有一致的分層可用；
兒科部日後要新增 Tier 6 或其他分類，直接在後台加即可，不需再改程式。

定位說明取自正式文件（四）的表格。
"""

from django.db import migrations

TIERS = [
    ("tier0", "Tier 0 基礎健康與兒童基本資料", 0,
     "可建立首次／基礎資料問卷，並設定於特定時期或首次使用時呈現。"),
    ("tier1", "Tier 1 日常低負擔健康檢核", 1,
     "以少量題目快速完成日常紀錄；健康狀況正常時不顯示不必要追問題目。"),
    ("tier2", "Tier 2 定向健康篩檢", 2,
     "依 Tier 1 或其他問卷之特定答案／條件，觸發進一步題組或量表。"),
    ("tier3", "Tier 3 疾病或特定健康議題追蹤", 3,
     "依個案疾病、追蹤狀態或指定條件持續採集特定健康資料。"),
    ("tier4", "Tier 4 情緒、心理或行為資料採集", 4,
     "支援相關題組、量表及特定期間之追蹤設定。"),
    ("tier5", "Tier 5 運動、活動及功能發展資料採集", 5,
     "支援運動、功能、活動能力或發展相關問卷之建立與追蹤。"),
]

CATEGORIES = [
    ("health_mgmt", "健康管理", 1),
    ("daily_tracking", "日常追蹤", 2),
    ("disease", "疾病", 3),
    ("psychology", "心理", 4),
    ("function", "功能", 5),
]


def seed(apps, schema_editor):
    Tier = apps.get_model("questionnaires", "Tier")
    Category = apps.get_model("questionnaires", "Category")
    for code, name, order, desc in TIERS:
        Tier.objects.update_or_create(
            code=code, defaults={"name": name, "order": order, "description": desc},
        )
    for code, name, order in CATEGORIES:
        Category.objects.update_or_create(
            code=code, defaults={"name": name, "order": order},
        )


def unseed(apps, schema_editor):
    Tier = apps.get_model("questionnaires", "Tier")
    Category = apps.get_model("questionnaires", "Category")
    Tier.objects.filter(code__in=[c for c, *_ in TIERS]).delete()
    Category.objects.filter(code__in=[c for c, *_ in CATEGORIES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("questionnaires", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
