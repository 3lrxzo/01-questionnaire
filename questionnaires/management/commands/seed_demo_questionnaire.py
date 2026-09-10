"""建立正式文件圖 2 的「發燒條件式追問」示範問卷。

這是 Phase 1 的端對端驗證情境（《開發規劃書》第九節第 6 點）：

    「孩子今天是否有發燒？」
      → 答「沒有」：直接進入下一項日常健康紀錄
      → 答「有」  ：顯示追問題組（最高體溫／持續時間／是否使用退燒藥）

用法：
    python manage.py seed_demo_questionnaire            # 建立（已存在則跳過）
    python manage.py seed_demo_questionnaire --publish  # 建立後直接發布 v1
    python manage.py seed_demo_questionnaire --reset    # 先刪掉舊的再重建

刻意寫成 management command 而非 fixture：內容可讀、邏輯自明，三台開發機
執行同一個指令即可得到一致的示範資料。
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from questionnaires.models import (
    BranchRule, EligibilityRule, Option, Question, Questionnaire,
    QuestionnaireVersion, Section, Tier,
)

QUESTIONNAIRE_NAME = "每日健康檢核（示範）"


class Command(BaseCommand):
    help = "建立發燒條件式追問的示範問卷（Phase 1 端對端驗證情境）"

    def add_arguments(self, parser):
        parser.add_argument("--publish", action="store_true", help="建立後直接發布 v1")
        parser.add_argument("--reset", action="store_true", help="先刪除既有示範問卷再重建")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            deleted, _ = Questionnaire.objects.filter(name=QUESTIONNAIRE_NAME).delete()
            if deleted:
                self.stdout.write(self.style.WARNING(f"已刪除舊的示範問卷（{deleted} 筆關聯物件）"))

        if Questionnaire.objects.filter(name=QUESTIONNAIRE_NAME).exists():
            self.stdout.write(self.style.NOTICE("示範問卷已存在，略過。加 --reset 可重建。"))
            return

        tier1 = Tier.objects.filter(code="tier1").first()
        questionnaire = Questionnaire.objects.create(
            name=QUESTIONNAIRE_NAME,
            description="每日一次的低負擔健康紀錄；若當日有發燒，才追問發燒細節。",
            tier=tier1,
        )
        version = QuestionnaireVersion.objects.create(
            questionnaire=questionnaire, version_number=1,
            change_note="示範用初版",
        )

        # 適用規則：0～72 個月（0～6 歲），每日填答
        EligibilityRule.objects.create(
            version=version, min_age_months=0, max_age_months=72,
            condition_json={"frequency": "daily"},
        )

        # --- 題組 1：每日必填 ---
        daily = Section.objects.create(version=version, title="每日必填", order=1)

        fever = Question.objects.create(
            section=daily, prompt="孩子今天是否有發燒？",
            question_type=Question.Type.SINGLE, order=1, required=True,
        )
        Option.objects.create(question=fever, label="沒有", value="no", order=1)
        Option.objects.create(question=fever, label="有", value="yes", order=2)

        Question.objects.create(
            section=daily, prompt="今天的活動力如何？",
            question_type=Question.Type.SCALE, order=2, required=True,
            config={"min": 0, "max": 10, "min_label": "非常虛弱", "max_label": "活蹦亂跳"},
        )

        # --- 題組 2：發燒追問（預設隱藏，由分支觸發）---
        fever_followup = Section.objects.create(
            version=version, title="發燒追問", order=2, is_active=True,
            description="僅在『今天是否有發燒＝有』時顯示",
        )
        Question.objects.create(
            section=fever_followup, prompt="今天測到的最高體溫是幾度？",
            question_type=Question.Type.NUMBER, order=1, required=True,
            config={"min": 35, "max": 42, "step": 0.1, "unit": "°C"},
        )
        Question.objects.create(
            section=fever_followup, prompt="從開始發燒到現在大約持續多久？",
            question_type=Question.Type.SINGLE, order=2, required=True,
        )
        duration = Question.objects.get(section=fever_followup, order=2)
        for i, (label, value) in enumerate(
            [("不到 1 天", "lt_1d"), ("1～2 天", "1_2d"), ("超過 3 天", "gt_3d")], start=1
        ):
            Option.objects.create(question=duration, label=label, value=value, order=i)
        meds = Question.objects.create(
            section=fever_followup, prompt="是否有使用退燒藥？",
            question_type=Question.Type.SINGLE, order=3, required=True,
        )
        Option.objects.create(question=meds, label="沒有", value="no", order=1)
        Option.objects.create(question=meds, label="有", value="yes", order=2)

        # --- 分支：發燒＝有 → 顯示追問題組 ---
        BranchRule.objects.create(
            trigger_question=fever,
            trigger_operator=BranchRule.Operator.EQ,
            trigger_value="yes",
            action=BranchRule.Action.SHOW,
            target_section=fever_followup,
        )

        self.stdout.write(self.style.SUCCESS(
            f"已建立「{QUESTIONNAIRE_NAME}」v1（草稿）："
            f"{version.sections.count()} 個題組、"
            f"{Question.objects.filter(section__version=version).count()} 題、"
            f"1 條分支規則"
        ))

        if options["publish"]:
            version.publish()
            self.stdout.write(self.style.SUCCESS("已發布 v1。"))
