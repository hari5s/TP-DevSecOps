import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import Task


class SecurityRegressionTests(TestCase):
    def setUp(self):
        self.task = Task.objects.create(title="Tache existante")

    def test_titles_are_escaped_in_list_and_search(self):
        title = "<script>alert(1)</script>"
        task = Task.objects.create(title=title)
        for complete in (False, True):
            task.complete = complete
            task.save()
            for url in (reverse("list"), reverse("search")):
                with self.subTest(complete=complete, url=url):
                    response = self.client.get(url)
                    self.assertContains(
                        response, "&lt;script&gt;alert(1)&lt;/script&gt;"
                    )
                    self.assertNotContains(response, title)

    def test_search_filters_results(self):
        response = self.client.get(reverse("search"), {"q": "existante"})
        self.assertContains(response, self.task.title)
        response = self.client.get(reverse("search"), {"q": "' OR 1=1 --"})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.task.title)

    def test_invalid_creation_does_not_save(self):
        count = Task.objects.count()
        response = self.client.post(reverse("list"), {"title": ""})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(Task.objects.count(), count)

    def test_invalid_update_preserves_task(self):
        response = self.client.post(
            reverse("update_task", args=[self.task.pk]), {"title": ""}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "Tache existante")

    def test_missing_tasks_return_404(self):
        for name in ("update_task", "delete"):
            response = self.client.get(reverse(name, args=[999999]))
            self.assertEqual(response.status_code, 404)

    def test_delete_ignores_external_redirect(self):
        response = self.client.post(
            reverse("delete", args=[self.task.pk]) + "?next=https://example.org"
        )
        self.assertRedirects(response, reverse("list"))
        self.assertFalse(Task.objects.filter(pk=self.task.pk).exists())

    def test_import_form_has_csrf_token(self):
        response = self.client.get(reverse("import_tasks"))
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_valid_import_creates_tasks(self):
        response = self.client.post(
            reverse("import_tasks"),
            {"tasks_data": json.dumps(["Import A", "Import B"])},
        )
        self.assertRedirects(response, reverse("list"))
        self.assertEqual(
            Task.objects.filter(title__in=["Import A", "Import B"]).count(), 2
        )

    def test_invalid_imports_create_nothing(self):
        payloads = [
            "not json",
            "{}",
            json.dumps(["x"] * 101),
            json.dumps([42]),
            json.dumps([""]),
            json.dumps(["x" * 201]),
            json.dumps(["Valide", ""]),
            "x" * 100001,
        ]
        count = Task.objects.count()
        for payload in payloads:
            with self.subTest(payload_length=len(payload)):
                response = self.client.post(
                    reverse("import_tasks"), {"tasks_data": payload}
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(Task.objects.count(), count)

    def test_post_without_csrf_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        urls = [
            reverse("list"),
            reverse("update_task", args=[self.task.pk]),
            reverse("delete", args=[self.task.pk]),
            reverse("import_tasks"),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(client.post(url, {}).status_code, 403)
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())

    def test_admin_panel_rejects_anonymous_and_regular_users(self):
        url = reverse("admin_panel")
        self.assertEqual(self.client.get(url).status_code, 302)
        user = get_user_model().objects.create_user(username="regular")
        self.client.force_login(user)
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_admin_panel_allows_staff_without_exposing_secret(self):
        user = get_user_model().objects.create_user(
            username="staff", is_staff=True
        )
        self.client.force_login(user)
        response = self.client.get(reverse("admin_panel"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, settings.SECRET_KEY)

    def test_unsupported_method_is_rejected(self):
        response = self.client.put(reverse("list"))
        self.assertEqual(response.status_code, 405)