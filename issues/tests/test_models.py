import pytest
from django.contrib.auth import get_user_model
from issues.models import Project, Issue, Comment

User = get_user_model()

@pytest.mark.django_db
def test_project_creation():
    project = Project.objects.create(name="Test Project", description="Project description")
    assert project.name == "Test Project"
    assert project.description == "Project description"
    # Check relation – project has no issues at the beginning
    assert project.issues.count() == 0

@pytest.mark.django_db
def test_issue_creation():
    user = User.objects.create_user(username="tester", password="pass")
    project = Project.objects.create(name="Test Project")
    issue = Issue.objects.create(
        project=project,
        title="Bug #1",
        description="Something is broken",
        assignee=user
    )
    # Check default status
    assert issue.status == "todo"
    # Check assigned user
    assert issue.assignee.username == "tester"
    # Check relation with project
    assert issue.project.issues.count() == 1

@pytest.mark.django_db
def test_issue_status_and_assignee():
    user = User.objects.create_user(username="tester2", password="pass")
    project = Project.objects.create(name="Test Project")
    issue = Issue.objects.create(
        project=project,
        title="Bug #2",
        description="Bug description",
        assignee=user
    )
    assert issue.status == "todo"
    assert issue.assignee.username == "tester2"
    assert issue.project.issues.count() == 1

@pytest.mark.django_db
def test_comment_creation():
    user = User.objects.create_user(username="commenter", password="pass")
    project = Project.objects.create(name="Test Project")
    issue = Issue.objects.create(project=project, title="Bug #3", description="Description")
    comment = Comment.objects.create(issue=issue, author=user, text="Test comment")

    # Check comment text
    assert comment.text == "Test comment"
    # Check relation with issue
    assert comment.issue == issue
    # Check comment author
    assert comment.author.username == "commenter"
    # Check relation in issue.comments
    assert issue.comments.count() == 1
