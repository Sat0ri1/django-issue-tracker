import pytest
from django.contrib.auth.models import User
from issues.models import Project, Issue, Comment

@pytest.mark.django_db
def test_issue_creation():
    user = User.objects.create(username="tester")
    project = Project.objects.create(name="Test Project")
    issue = Issue.objects.create(
        project=project, title="Bug #1", description="Something is broken", assignee=user
    )
    assert issue.status == "todo"
    assert issue.assignee.username == "tester"


@pytest.mark.django_db
def test_project_creation():
    project = Project.objects.create(name="Projekt Testowy", description="Opis projektu")
    assert project.name == "Projekt Testowy"
    assert project.description == "Opis projektu"
    # Sprawdzenie relacji
    assert project.issues.count() == 0

@pytest.mark.django_db
def test_issue_status_and_assignee():
    user = User.objects.create(username="tester2")
    project = Project.objects.create(name="Projekt Testowy")
    issue = Issue.objects.create(
        project=project, title="Bug #2", description="Opis błędu", assignee=user
    )
    # Domyślny status
    assert issue.status == "todo"
    # Sprawdzenie przypisania do użytkownika
    assert issue.assignee.username == "tester2"
    # Sprawdzenie relacji do projektu
    assert issue.project.issues.count() == 1

@pytest.mark.django_db
def test_comment_creation():
    user = User.objects.create(username="komentator")
    project = Project.objects.create(name="Projekt Testowy")
    issue = Issue.objects.create(project=project, title="Bug #3", description="Opis")
    comment = Comment.objects.create(issue=issue, author=user, text="Komentarz testowy")

    # Sprawdzenie treści komentarza
    assert comment.text == "Komentarz testowy"
    # Sprawdzenie powiązania z issue
    assert comment.issue == issue
    # Sprawdzenie autora komentarza
    assert comment.author.username == "komentator"
    # Sprawdzenie relacji w issue.comments
    assert issue.comments.count() == 1