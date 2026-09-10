from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from children.models import Child


class RegistrationFlowTests(TestCase):
    def test_register_creates_user_logs_in_and_goes_to_add_child(self):
        res = self.client.post(reverse("accounts:register"), {
            "username": "parent01",
            "full_name": "王小明",
            "email": "p1@example.com",
            "password1": "veryStrongPw!23",
            "password2": "veryStrongPw!23",
        })
        self.assertRedirects(res, reverse("questionnaires:child-add"))
        user = User.objects.get(username="parent01")
        self.assertEqual(user.first_name, "王小明")
        self.assertEqual(user.email, "p1@example.com")
        # 已登入
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_register_rejects_mismatched_passwords(self):
        res = self.client.post(reverse("accounts:register"), {
            "username": "p", "full_name": "x", "email": "x@example.com",
            "password1": "veryStrongPw!23", "password2": "different!45",
        })
        self.assertEqual(res.status_code, 200)
        self.assertFalse(User.objects.filter(username="p").exists())

    def test_login_then_logout(self):
        User.objects.create_user("parent02", password="pw12345678")
        res = self.client.post(reverse("accounts:login"), {
            "username": "parent02", "password": "pw12345678",
        })
        self.assertRedirects(res, reverse("questionnaires:parent-home"),
                             fetch_redirect_response=False)
        res = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(res, reverse("questionnaires:landing"),
                             fetch_redirect_response=False)


class ChildRegistrationTests(TestCase):
    def setUp(self):
        self.parent = User.objects.create_user("parent", password="pw12345678")
        self.client.force_login(self.parent)

    def test_add_child_binds_to_current_user_and_redirects_to_child_home(self):
        res = self.client.post(reverse("questionnaires:child-add"), {
            "name": "王小寶",
            "birth_date": "2023-01-15",
            "medical_no": "",
            "tracking_status": "",
        })
        child = Child.objects.get(name="王小寶")
        self.assertEqual(child.guardian, self.parent)
        self.assertRedirects(
            res, reverse("questionnaires:child-home", args=[child.id]),
            fetch_redirect_response=False,
        )

    def test_add_child_requires_login(self):
        self.client.logout()
        res = self.client.get(reverse("questionnaires:child-add"))
        self.assertEqual(res.status_code, 302)
        self.assertIn("/accounts/login/", res["Location"])


class LandingTests(TestCase):
    def test_landing_is_public_and_shows_both_roles(self):
        res = self.client.get(reverse("questionnaires:landing"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "家長")
        self.assertContains(res, "醫護人員")
