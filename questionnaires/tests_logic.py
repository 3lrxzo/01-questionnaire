"""logic.py 的測試：分支判斷、適用規則、待填問卷推導。"""

from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from children.models import Child

from .logic import (
    child_matches_version,
    compute_visibility,
    evaluate_condition,
    get_pending_questionnaires,
)
from .models import (
    BranchRule, EligibilityRule, Option, Question, Questionnaire,
    QuestionnaireResponse, QuestionnaireVersion, Section, Tier,
)


class EvaluateConditionTests(TestCase):
    def test_eq_and_neq(self):
        self.assertTrue(evaluate_condition("eq", "yes", "yes"))
        self.assertFalse(evaluate_condition("eq", "yes", "no"))
        self.assertTrue(evaluate_condition("neq", "yes", "no"))

    def test_answered(self):
        self.assertTrue(evaluate_condition("answered", "", "anything"))
        self.assertFalse(evaluate_condition("answered", "", None))
        self.assertFalse(evaluate_condition("answered", "", []))
        self.assertFalse(evaluate_condition("answered", "", ""))

    def test_numeric_operators(self):
        self.assertTrue(evaluate_condition("gte", "38", "38.5"))
        self.assertTrue(evaluate_condition("gt", "38", 39))
        self.assertFalse(evaluate_condition("gt", "38", 37))
        self.assertTrue(evaluate_condition("lt", "38", "37.2"))

    def test_in_operator(self):
        self.assertTrue(evaluate_condition("in", "a,b,c", "b"))
        self.assertFalse(evaluate_condition("in", "a,b,c", "d"))

    def test_multi_select_answer_hits_if_any_option_matches(self):
        self.assertTrue(evaluate_condition("eq", "fever", ["cough", "fever"]))
        self.assertFalse(evaluate_condition("eq", "fever", ["cough", "runny_nose"]))

    def test_none_answer_never_hits_except_answered(self):
        self.assertFalse(evaluate_condition("eq", "yes", None))
        self.assertFalse(evaluate_condition("gt", "0", None))


class FeverFixtureMixin:
    def build_published_fever_version(self, eligibility=None):
        """建立並發布發燒示範版本。

        eligibility：欲掛在版本上的 EligibilityRule 參數 dict（可選）。
        必須在 publish 前建立 —— EligibilityRule 是版本內容，發布後就鎖住
        （正式文件（八）：適用規則調整須建新版本）。
        """
        tier, _ = Tier.objects.get_or_create(code="tier1", defaults={"name": "Tier 1", "order": 1})
        questionnaire = Questionnaire.objects.create(name="每日健康檢核", tier=tier)
        version = QuestionnaireVersion.objects.create(questionnaire=questionnaire, version_number=1)

        daily = Section.objects.create(version=version, title="每日必填", order=1)
        self.fever = Question.objects.create(
            section=daily, prompt="今天是否有發燒？", question_type=Question.Type.SINGLE, order=1,
        )
        Option.objects.create(question=self.fever, label="沒有", value="no", order=1)
        Option.objects.create(question=self.fever, label="有", value="yes", order=2)
        self.activity = Question.objects.create(
            section=daily, prompt="活動力如何？", question_type=Question.Type.SCALE, order=2,
        )

        self.followup = Section.objects.create(version=version, title="發燒追問", order=2)
        self.temp = Question.objects.create(
            section=self.followup, prompt="最高體溫？", question_type=Question.Type.NUMBER, order=1,
        )

        BranchRule.objects.create(
            trigger_question=self.fever, trigger_operator=BranchRule.Operator.EQ,
            trigger_value="yes", action=BranchRule.Action.SHOW, target_section=self.followup,
        )

        if eligibility is not None:
            EligibilityRule.objects.create(version=version, **eligibility)

        version.publish()
        self.version = version
        self.daily = daily
        return version


class ComputeVisibilityTests(FeverFixtureMixin, TestCase):
    def setUp(self):
        self.build_published_fever_version()

    def test_followup_hidden_when_no_fever(self):
        result = compute_visibility(self.version, {self.fever.id: "no"})
        self.assertNotIn(self.followup.id, result["visible_section_ids"])
        self.assertNotIn(self.temp.id, result["visible_question_ids"])
        # 每日必填題組始終可見
        self.assertIn(self.daily.id, result["visible_section_ids"])
        self.assertIn(self.fever.id, result["visible_question_ids"])
        self.assertIn(self.activity.id, result["visible_question_ids"])

    def test_followup_shown_when_fever_yes(self):
        result = compute_visibility(self.version, {self.fever.id: "yes"})
        self.assertIn(self.followup.id, result["visible_section_ids"])
        self.assertIn(self.temp.id, result["visible_question_ids"])

    def test_no_answer_yet_keeps_followup_hidden(self):
        result = compute_visibility(self.version, {})
        self.assertNotIn(self.followup.id, result["visible_section_ids"])

    def test_hidden_section_hides_its_questions(self):
        result = compute_visibility(self.version, {self.fever.id: "no"})
        for qid in result["visible_question_ids"]:
            self.assertNotEqual(qid, self.temp.id)


class CrossQuestionnaireTriggerTests(TestCase):
    def test_show_rule_can_trigger_another_questionnaire(self):
        tier2, _ = Tier.objects.get_or_create(code="tier2", defaults={"name": "Tier 2", "order": 2})
        screening = Questionnaire.objects.create(name="定向篩檢", tier=tier2)

        tier1, _ = Tier.objects.get_or_create(code="tier1", defaults={"name": "Tier 1", "order": 1})
        daily = Questionnaire.objects.create(name="日常檢核", tier=tier1)
        version = QuestionnaireVersion.objects.create(questionnaire=daily, version_number=1)
        section = Section.objects.create(version=version, title="每日", order=1)
        q = Question.objects.create(
            section=section, prompt="連續三天發燒？", question_type=Question.Type.SINGLE, order=1,
        )
        BranchRule.objects.create(
            trigger_question=q, trigger_operator=BranchRule.Operator.EQ,
            trigger_value="yes", action=BranchRule.Action.SHOW,
            target_questionnaire=screening,
        )
        version.publish()

        hit = compute_visibility(version, {q.id: "yes"})
        miss = compute_visibility(version, {q.id: "no"})
        self.assertIn(screening.id, hit["triggered_questionnaire_ids"])
        self.assertNotIn(screening.id, miss["triggered_questionnaire_ids"])


class EligibilityTests(FeverFixtureMixin, TestCase):
    def _child_aged_months(self, months, **kwargs):
        birth = timezone.localdate() - timedelta(days=int(months * 30.44))
        return Child.objects.create(name="測試童", birth_date=birth, **kwargs)

    def test_no_rules_means_applies_to_everyone(self):
        version = self.build_published_fever_version()
        self.assertTrue(child_matches_version(self._child_aged_months(200), version))

    def test_age_range(self):
        version = self.build_published_fever_version(
            eligibility={"min_age_months": 0, "max_age_months": 72}
        )
        self.assertTrue(child_matches_version(self._child_aged_months(36), version))
        self.assertFalse(child_matches_version(self._child_aged_months(90), version))

    def test_tracking_status_must_match_when_specified(self):
        version = self.build_published_fever_version(
            eligibility={"tracking_status": "氣喘追蹤"}
        )
        matched = self._child_aged_months(36, tracking_status="氣喘追蹤")
        other = self._child_aged_months(36, tracking_status="一般")
        self.assertTrue(child_matches_version(matched, version))
        self.assertFalse(child_matches_version(other, version))


class PendingQuestionnairesTests(FeverFixtureMixin, TestCase):
    def setUp(self):
        self.build_published_fever_version(
            eligibility={"min_age_months": 0, "max_age_months": 72}
        )
        self.child = Child.objects.create(
            name="小明", birth_date=timezone.localdate() - timedelta(days=365 * 3),
        )

    def test_unrecorded_when_no_response_exists(self):
        pending = get_pending_questionnaires(self.child)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["state"], "unrecorded")
        self.assertIsNone(pending[0]["response_id"])

    def test_in_progress_when_response_started(self):
        response = QuestionnaireResponse.objects.create(child=self.child, version=self.version)
        pending = get_pending_questionnaires(self.child)
        self.assertEqual(pending[0]["state"], "in_progress")
        self.assertEqual(pending[0]["response_id"], response.id)

    def test_completed_is_not_pending(self):
        r = QuestionnaireResponse.objects.create(child=self.child, version=self.version)
        r.mark_completed()
        self.assertEqual(get_pending_questionnaires(self.child), [])

    def test_child_outside_age_range_has_nothing_pending(self):
        old_child = Child.objects.create(
            name="大華", birth_date=timezone.localdate() - timedelta(days=365 * 10),
        )
        self.assertEqual(get_pending_questionnaires(old_child), [])

    def test_only_latest_published_version_is_offered(self):
        v2 = self.version.clone_as_new_draft()
        v2.publish()
        pending = get_pending_questionnaires(self.child)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["version"].version_number, 2)

    def test_draft_only_questionnaire_is_not_offered(self):
        tier0, _ = Tier.objects.get_or_create(code="tier0", defaults={"name": "Tier 0", "order": 0})
        q = Questionnaire.objects.create(name="尚未發布的問卷", tier=tier0)
        QuestionnaireVersion.objects.create(questionnaire=q, version_number=1)  # 草稿
        pending = get_pending_questionnaires(self.child)
        names = [p["version"].questionnaire.name for p in pending]
        self.assertNotIn("尚未發布的問卷", names)
