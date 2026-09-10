"""版本不可覆寫與分支目標約束的回歸測試。

這兩件事是《系統功能與功能架構設計 V1.0》第（八）（九）（十）節反覆
要求的核心約束，一旦破功就是無聲的歷史資料毀損（改一份已發布問卷的
題目文字，既有填答的語意會跟著變，但沒有任何錯誤訊息）。因此獨立成
測試，避免日後重構時被摘掉。
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import (
    BranchRule, Option, Question, Questionnaire, QuestionnaireVersion, Section, Tier,
)


class VersionFixtureMixin:
    def build_draft_version(self):
        tier = Tier.objects.create(code="tier1", name="Tier 1 日常低負擔健康檢核", order=1)
        questionnaire = Questionnaire.objects.create(name="每日健康檢核", tier=tier)
        version = QuestionnaireVersion.objects.create(questionnaire=questionnaire, version_number=1)
        section = Section.objects.create(version=version, title="每日必填", order=1)
        fever = Question.objects.create(
            section=section, prompt="孩子今天是否有發燒？",
            question_type=Question.Type.SINGLE, order=1,
        )
        Option.objects.create(question=fever, label="沒有", value="no", order=1)
        Option.objects.create(question=fever, label="有", value="yes", order=2)
        followup = Section.objects.create(version=version, title="發燒追問", order=2)
        Question.objects.create(
            section=followup, prompt="最高體溫？",
            question_type=Question.Type.NUMBER, order=1,
            config={"min": 35, "max": 42, "step": 0.1, "unit": "°C"},
        )
        BranchRule.objects.create(
            trigger_question=fever, trigger_value="yes", target_section=followup,
        )
        return version, section, fever, followup


class PublishedVersionIsImmutableTests(VersionFixtureMixin, TestCase):
    def setUp(self):
        self.version, self.section, self.fever, self.followup = self.build_draft_version()

    def test_draft_content_is_editable(self):
        self.fever.prompt = "改過的題目"
        self.fever.save()
        self.assertEqual(Question.objects.get(pk=self.fever.pk).prompt, "改過的題目")

    def test_cannot_edit_question_of_published_version(self):
        self.version.publish()
        self.fever.prompt = "被竄改的題目"
        with self.assertRaises(ValidationError):
            self.fever.save()
        self.assertEqual(Question.objects.get(pk=self.fever.pk).prompt, "孩子今天是否有發燒？")

    def test_cannot_edit_option_of_published_version(self):
        self.version.publish()
        option = self.fever.options.first()
        option.label = "被竄改的選項"
        with self.assertRaises(ValidationError):
            option.save()

    def test_cannot_add_question_to_published_version(self):
        self.version.publish()
        with self.assertRaises(ValidationError):
            Question.objects.create(
                section=self.section, prompt="偷加的題目",
                question_type=Question.Type.TEXT, order=99,
            )

    def test_cannot_delete_section_of_published_version(self):
        self.version.publish()
        with self.assertRaises(ValidationError):
            self.followup.delete()

    def test_publish_requires_at_least_one_question(self):
        empty = QuestionnaireVersion.objects.create(
            questionnaire=self.version.questionnaire, version_number=99,
        )
        with self.assertRaises(ValidationError):
            empty.publish()

    def test_cannot_publish_twice(self):
        self.version.publish()
        with self.assertRaises(ValidationError):
            self.version.publish()

    def test_cannot_revert_published_to_draft(self):
        """把已發布版本改回草稿就能繞過內容鎖，必須擋在狀態轉換這關。"""
        self.version.publish()
        self.version.status = QuestionnaireVersion.Status.DRAFT
        with self.assertRaises(ValidationError):
            self.version.save()
        self.assertEqual(
            QuestionnaireVersion.objects.get(pk=self.version.pk).status,
            QuestionnaireVersion.Status.PUBLISHED,
        )

    def test_cannot_revert_retired_to_draft(self):
        self.version.publish()
        self.version.retire()
        self.version.status = QuestionnaireVersion.Status.DRAFT
        with self.assertRaises(ValidationError):
            self.version.save()

    def test_cannot_reactivate_retired_version(self):
        self.version.publish()
        self.version.retire()
        self.version.status = QuestionnaireVersion.Status.PUBLISHED
        with self.assertRaises(ValidationError):
            self.version.save()

    def test_draft_to_published_transition_is_allowed(self):
        self.version.status = QuestionnaireVersion.Status.PUBLISHED
        self.version.save()
        self.assertEqual(
            QuestionnaireVersion.objects.get(pk=self.version.pk).status,
            QuestionnaireVersion.Status.PUBLISHED,
        )


class CloneAsNewDraftTests(VersionFixtureMixin, TestCase):
    def setUp(self):
        self.version, self.section, self.fever, self.followup = self.build_draft_version()
        self.version.publish()

    def test_clone_copies_whole_tree_and_is_editable(self):
        v2 = self.version.clone_as_new_draft()

        self.assertEqual(v2.version_number, 2)
        self.assertEqual(v2.status, QuestionnaireVersion.Status.DRAFT)
        self.assertEqual(v2.sections.count(), 2)
        self.assertEqual(Question.objects.filter(section__version=v2).count(), 2)
        self.assertEqual(Option.objects.filter(question__section__version=v2).count(), 2)

        question = Question.objects.filter(section__version=v2, prompt=self.fever.prompt).get()
        question.prompt = "v2 改過的題目"
        question.save()  # 草稿，不應拋錯

    def test_clone_rewires_branch_rules_to_the_new_version(self):
        v2 = self.version.clone_as_new_draft()
        rule = BranchRule.objects.get(trigger_question__section__version=v2)

        # 分支必須指向新版本自己的題組，不能還指著 v1 的
        self.assertEqual(rule.target_section.version_id, v2.pk)
        self.assertEqual(rule.trigger_question.section.version_id, v2.pk)
        self.assertNotEqual(rule.target_section_id, self.followup.pk)

    def test_editing_clone_does_not_affect_the_published_original(self):
        v2 = self.version.clone_as_new_draft()
        question = Question.objects.filter(section__version=v2, prompt=self.fever.prompt).get()
        question.prompt = "v2 改過的題目"
        question.save()

        self.assertEqual(Question.objects.get(pk=self.fever.pk).prompt, "孩子今天是否有發燒？")


class BranchRuleTargetConstraintTests(VersionFixtureMixin, TestCase):
    def setUp(self):
        self.version, self.section, self.fever, self.followup = self.build_draft_version()

    def _create(self, **kwargs):
        with transaction.atomic():
            return BranchRule.objects.create(
                trigger_question=self.fever, trigger_value="yes", **kwargs
            )

    def test_rejects_multiple_targets(self):
        with self.assertRaises(IntegrityError):
            self._create(
                target_section=self.followup,
                target_questionnaire=self.version.questionnaire,
            )

    def test_rejects_no_target(self):
        with self.assertRaises(IntegrityError):
            self._create()

    def test_accepts_exactly_one_target(self):
        self.assertIsNotNone(self._create(target_section=self.followup))
        self.assertIsNotNone(self._create(target_question=self.fever))
        self.assertIsNotNone(self._create(target_questionnaire=self.version.questionnaire))
