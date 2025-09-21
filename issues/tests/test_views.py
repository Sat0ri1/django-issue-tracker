import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from issues.models import Project, Issue, Comment

@pytest.mark.django_db
def test_project_list_view(client):
    Project.objects.create(name="P1")
    r = client.get(reverse("project_list"))
    assert r.status_code == 200
    assert b"P1" in r.content

@pytest.mark.django_db
def test_create_issue_requires_login(client):
    project = Project.objects.create(name="P2")
    url = reverse("create_issue", kwargs={"project_pk": project.pk})
    response = client.post(url, {"title": "Test", "description": "Test"})
    assert response.status_code == 302

@pytest.mark.django_db
def test_add_comment_requires_login(client):
    project = Project.objects.create(name="P3")
    issue = Issue.objects.create(project=project, title="Bug", description="desc")
    url = reverse("add_comment", kwargs={"issue_pk": issue.pk})
    response = client.post(url, {"text": "Komentarz"})
    assert response.status_code == 302

@pytest.mark.django_db
def test_change_status_requires_login(client):
    project = Project.objects.create(name="P4")
    issue = Issue.objects.create(project=project, title="Bug", description="desc")
    url = reverse("change_status", kwargs={"pk": issue.pk})
    response = client.post(url, {"status": "done"})
    assert response.status_code == 302

@pytest.mark.django_db
def test_create_issue_logged_in(client):
    user = User.objects.create_user(username="tester", password="pass")
    client.login(username=user.username, password="pass")
    project = Project.objects.create(name="P5")
    url = reverse("create_issue", kwargs={"project_pk": project.pk})
    response = client.post(url, {"title": "BugY", "description": "desc"})
    assert response.status_code == 302
    issue = Issue.objects.get(title="BugY")
    assert issue.project == project

@pytest.mark.django_db
def test_add_comment_logged_in(client):
    user = User.objects.create_user(username="commenter", password="pass")
    client.login(username=user.username, password="pass")
    project = Project.objects.create(name="P6")
    issue = Issue.objects.create(project=project, title="Bug", description="desc")
    url = reverse("add_comment", kwargs={"issue_pk": issue.pk})
    response = client.post(url, {"text": "Komentarz"})
    assert response.status_code == 302
    comment = Comment.objects.get(text="Komentarz")
    assert comment.issue == issue
    assert comment.author == user

@pytest.mark.django_db
def test_change_status_logged_in(client):
    user = User.objects.create_user(username="tester2", password="pass")
    client.login(username=user.username, password="pass")
    project = Project.objects.create(name="P7")
    issue = Issue.objects.create(project=project, title="Bug", description="desc")
    url = reverse("change_status", kwargs={"pk": issue.pk})
    response = client.post(url, {"status": "done"})
    assert response.status_code == 302
    issue.refresh_from_db()
    assert issue.status == "done"

@pytest.mark.django_db
def test_logout_logs_user_out(client):
    user = User.objects.create_user(username="u1", password="pass")
    client.login(username=user.username, password="pass")
    r = client.get(reverse("project_list"))
    assert r.wsgi_request.user.is_authenticated
    response = client.post(reverse("logout"))
    assert response.status_code == 302 
    r2 = client.get(reverse("project_list"))
    assert not r2.wsgi_request.user.is_authenticated
