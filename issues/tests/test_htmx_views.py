import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from issues.models import Project, Issue, Comment

@pytest.mark.django_db
class TestHTMXViews:

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="alice", password="password123")

    @pytest.fixture
    def project(self):
        return Project.objects.create(name="Projekt Testowy")

    @pytest.fixture
    def issue(self, project, user):
        return Issue.objects.create(
            project=project, title="Bug #1", description="Opis błędu", author=user
        )

    # ---------------------------
    # create_issue
    # ---------------------------
    def test_create_issue_requires_login(self, client, project):
        url = reverse("create_issue", kwargs={"project_pk": project.pk})
        r = client.post(url, {"title": "HTMX Bug", "description": "desc"}, HTTP_HX_REQUEST="true")
        # niezalogowany → przekierowanie na login
        assert r.status_code == 302
        assert "/login/" in r.url

    def test_create_issue_logged_in(self, client, user, project):
        client.login(username="alice", password="password123")
        url = reverse("create_issue", kwargs={"project_pk": project.pk})
        data = {"title": "HTMX Bug", "description": "desc"}
        r = client.post(url, data, HTTP_HX_REQUEST="true")
        assert r.status_code == 200
        # Issue faktycznie dodane
        assert project.issues.filter(title="HTMX Bug").exists()
        assert b"HTMX Bug" in r.content

    # ---------------------------
    # add_comment
    # ---------------------------
    def test_add_comment_requires_login(self, client, issue):
        url = reverse("add_comment", kwargs={"issue_pk": issue.pk})
        r = client.post(url, {"text": "Nowy komentarz"}, HTTP_HX_REQUEST="true")
        assert r.status_code == 302
        assert "/login/" in r.url

    def test_add_comment_logged_in(self, client, user, issue):
        client.login(username="alice", password="password123")
        url = reverse("add_comment", kwargs={"issue_pk": issue.pk})
        data = {"text": "Nowy komentarz"}
        r = client.post(url, data, HTTP_HX_REQUEST="true")
        assert r.status_code == 200
        assert issue.comments.filter(text="Nowy komentarz").exists()
        assert b"Nowy komentarz" in r.content

    # ---------------------------
    # change_status
    # ---------------------------
    def test_change_status_requires_login(self, client, issue):
        url = reverse("change_status", kwargs={"pk": issue.pk})
        r = client.post(url, {"status": "in_progress"}, HTTP_HX_REQUEST="true")
        assert r.status_code == 302
        assert "/login/" in r.url

    def test_change_status_logged_in(self, client, user, issue):
        client.login(username="alice", password="password123")
        url = reverse("change_status", kwargs={"pk": issue.pk})
        r = client.post(url, {"status": "in_progress"}, HTTP_HX_REQUEST="true")
        assert r.status_code == 200
        issue.refresh_from_db()
        assert issue.status == "in_progress"
        # fragment HTMX zawiera tytuł issue
        assert bytes(issue.title, encoding="utf-8") in r.content
