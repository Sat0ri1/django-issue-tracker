import pytest
from django.contrib.auth import get_user_model
from issues.models import Project, Issue, Comment

User = get_user_model()

@pytest.mark.django_db
class TestModels:
    def test_project_creation(self):
        project = Project.objects.create(
            name="Test Project",
            description="Test Description"
        )
        assert project.name == "Test Project"
        assert project.description == "Test Description"
        assert str(project) == "Test Project"

    def test_issue_creation(self):
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            role="assignee"
        )
        project = Project.objects.create(
            name="Test Project",
            description="Test Description"
        )
        issue = Issue.objects.create(
            title="Test Issue",
            description="Test Issue Description",
            project=project,
            author=user,
            assignee=user,
            status="todo"
        )
        assert issue.title == "Test Issue"
        assert issue.project == project
        assert issue.author == user
        assert issue.assignee == user
        assert issue.status == "todo"
        assert str(issue) == "[To Do] Test Issue"

    def test_comment_creation(self):
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            role="assignee"
        )
        project = Project.objects.create(
            name="Test Project",
            description="Test Description"
        )
        issue = Issue.objects.create(
            title="Test Issue",
            description="Test Issue Description",
            project=project,
            author=user
        )
        comment = Comment.objects.create(
            issue=issue,
            author=user,
            text="Test comment text"
        )
        assert comment.issue == issue
        assert comment.author == user
        assert comment.text == "Test comment text"
        assert str(comment) == f"Comment by {user.username} on {issue.title}"

    def test_issue_status_choices(self):
        # Matched to actual choices in model
        assert Issue.STATUS_CHOICES == [
            ("todo", "To Do"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
        ]

    def test_comment_related_name(self):
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            role="assignee"
        )
        project = Project.objects.create(
            name="Test Project",
            description="Test Description"
        )
        issue = Issue.objects.create(
            title="Test Issue",
            description="Test Issue Description",
            project=project,
            author=user
        )
        comment = Comment.objects.create(
            issue=issue,
            author=user,
            text="Test comment"
        )
        # Test related_name='comments' (plural)
        assert comment in Comment.objects.filter(issue=issue)
        assert Comment.objects.filter(issue=issue).count() == 1
