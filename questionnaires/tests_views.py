"""家長端入口頁測試。"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from children.models import Child

from .models import (
    EligibilityRule, Question, Questionnaire, QuestionnaireResponse,
    QuestionnaireVersion, Section, Tier,
)


class ChildHomeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.parent = User.objects.create_user("parent", password="pw")
        self.other_parent = User.objects.create_user("other", password="pw")

        tier, _ = Tier.objects.get_or_create(code="tier1", defaults={"name": "Tier 1", "order": 1})
        self.q = Questionnaire.objects.create(name="每日健康檢核", tier=tier)
        self.version = QuestionnaireVersion.objects.create(questionnaire=self.q, version_number=1)
        section = Section.objects.create(version=self.version, title="每日", order=1)
        Question.objects.create(
            section=section, prompt="今天好嗎？", question_type=Question.Type.TEXT, order=1,
        )
        EligibilityRule.objects.create(version=self.version, min_age_months=0, max_age_months=120)
        self.version.publish()

        self.child = Child.objects.create(
            name="小明", birth_date=timezone.localdate() - timedelta(days=365 * 3),
            guardian=self.parent,
        )

    def test_unrecorded_questionnaire_shows_as_pending(self):
        self.client.force_login(self.parent)
        res = self.client.get(reverse("questionnaires:child-home", args=[self.child.id]))
        self.assertContains(res, "每日健康檢核")
        self.assertContains(res, "未記錄")
        self.assertContains(res, "開始填答")

    def test_in_progress_shows_continue(self):
        QuestionnaireResponse.objects.create(child=self.child, version=self.version)
        self.client.force_login(self.parent)
        res = self.client.get(reverse("questionnaires:child-home", args=[self.child.id]))
        self.assertContains(res, "未完成")
        self.assertContains(res, "繼續填答")

    def test_completed_moves_to_history(self):
        r = QuestionnaireResponse.objects.create(child=self.child, version=self.version)
        r.mark_completed()
        self.client.force_login(self.parent)
        res = self.client.get(reverse("questionnaires:child-home", args=[self.child.id]))
        self.assertContains(res, "目前沒有需要填寫的問卷")
        self.assertContains(res, "已完成")

    def test_other_parent_cannot_view_this_child(self):
        self.client.force_login(self.other_parent)
        res = self.client.get(reverse("questionnaires:child-home", args=[self.child.id]))
        self.assertEqual(res.status_code, 404)

    def test_staff_can_view_any_child(self):
        User = get_user_model()
        staff = User.objects.create_user("staff", password="pw", is_staff=True)
        self.client.force_login(staff)
        res = self.client.get(reverse("questionnaires:child-home", args=[self.child.id]))
        self.assertEqual(res.status_code, 200)

    def test_parent_home_lists_children(self):
        Child.objects.create(
            name="小華", birth_date=timezone.localdate() - timedelta(days=365 * 5),
            guardian=self.parent,
        )
        self.client.force_login(self.parent)
        res = self.client.get(reverse("questionnaires:parent-home"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "小明")
        self.assertContains(res, "小華")

    def test_parent_home_redirects_to_add_when_no_children(self):
        User = get_user_model()
        childless = User.objects.create_user("childless", password="pw")
        self.client.force_login(childless)
        res = self.client.get(reverse("questionnaires:parent-home"))
        self.assertRedirects(
            res, reverse("questionnaires:child-add"), fetch_redirect_response=False,
        )

    def test_requires_login(self):
        res = self.client.get(reverse("questionnaires:child-home", args=[self.child.id]))
        self.assertEqual(res.status_code, 302)
        self.assertIn("/accounts/login/", res["Location"])
