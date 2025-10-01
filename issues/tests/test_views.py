import pytest
from django.test import Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from issues.models import Project, Issue, Comment

User = get_user_model()

@pytest.mark.django_db
class TestViews:
    def setup_method(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            role="admin"
        )
        self.assignee_user = User.objects.create_user(
            username="assignee",
            email="assignee@example.com",
            password="assigneepass123",
            role="assignee"
        )
        self.user = User.objects.create_user(
            username="user",
            email="user@example.com",
            password="userpass123",
            role="user"
        )
        self.project = Project.objects.create(
            name="Test Project",
            description="Test Description"
        )

    def test_project_list_view(self):
        response = self.client.get(reverse('project_list'))
        assert response.status_code == 200
        assert self.project.name.encode() in response.content

    def test_project_detail_view(self):
        response = self.client.get(reverse('project_detail', kwargs={'pk': self.project.pk}))
        assert response.status_code == 200
        assert self.project.name.encode() in response.content
        assert b'Komentarze' in response.content or b'Comments' in response.content

    def test_project_detail_with_issues_and_comments(self):
        issue = Issue.objects.create(
            title="Test Issue",
            description="Test Description",
            project=self.project,
            author=self.user
        )
        comment = Comment.objects.create(
            issue=issue,
            author=self.assignee_user,
            text="Test comment"
        )
        
        response = self.client.get(reverse('project_detail', kwargs={'pk': self.project.pk}))
        assert response.status_code == 200
        assert issue.title.encode() in response.content
        # Comments should be loaded for each issue
        assert 'comments_list' in str(response.content) or comment.text.encode() in response.content

    def test_issue_detail_view(self):
        issue = Issue.objects.create(
            title="Test Issue",
            description="Test Description",
            project=self.project,
            author=self.user
        )
        response = self.client.get(reverse('issue_detail', kwargs={'pk': issue.pk}))
        assert response.status_code == 200
        assert issue.title.encode() in response.content
        assert issue.description.encode() in response.content
        assert b'Komentarze' in response.content or b'Comments' in response.content

    def test_create_issue_authenticated_user(self):
        self.client.login(username='user', password='userpass123')
        response = self.client.post(reverse('create_issue', kwargs={'project_pk': self.project.pk}), {
            'title': 'New Issue',
            'description': 'New Issue Description',
            'priority': 'medium'
        })
        assert response.status_code == 302  # Redirect after creation
        assert Issue.objects.filter(title='New Issue').exists()

    def test_create_issue_unauthenticated_user(self):
        response = self.client.post(reverse('create_issue', kwargs={'project_pk': self.project.pk}), {
            'title': 'New Issue',
            'description': 'New Issue Description'
        })
        assert response.status_code == 302  # Redirect to login

    def test_add_comment_as_assignee(self):
        issue = Issue.objects.create(
            title="Test Issue",
            description="Test Description",
            project=self.project,
            author=self.user
        )
        self.client.login(username='assignee', password='assigneepass123')
        response = self.client.post(reverse('add_comment', kwargs={'issue_pk': issue.pk}), {
            'content': 'Test comment content'
        })
        assert response.status_code == 302  # Redirect after creation
        assert Comment.objects.filter(text='Test comment content').exists()

    def test_add_comment_as_admin(self):
        issue = Issue.objects.create(
            title="Test Issue",
            description="Test Description",
            project=self.project,
            author=self.user
        )
        self.client.login(username='admin', password='adminpass123')
        response = self.client.post(reverse('add_comment', kwargs={'issue_pk': issue.pk}), {
            'content': 'Admin comment'
        })
        assert response.status_code == 302
        assert Comment.objects.filter(text='Admin comment').exists()

    def test_add_comment_as_regular_user_forbidden(self):
        issue = Issue.objects.create(
            title="Test Issue",
            description="Test Description",
            project=self.project,
            author=self.user
        )
        self.client.login(username='user', password='userpass123')
        response = self.client.post(reverse('add_comment', kwargs={'issue_pk': issue.pk}), {
            'content': 'User comment'
        })
        assert response.status_code == 403  # Forbidden

    def test_change_status_as_assignee(self):
        issue = Issue.objects.create(
            title="Test Issue",
            description="Test Description",
            project=self.project,
            author=self.user,
            status="todo"
        )
        self.client.login(username='assignee', password='assigneepass123')
        response = self.client.post(reverse('change_status', kwargs={'pk': issue.pk}), {
            'status': 'in_progress'
        })
        assert response.status_code == 302
        issue.refresh_from_db()
        assert issue.status == 'in_progress'

    def test_create_project_as_admin(self):
        self.client.login(username='admin', password='adminpass123')
        response = self.client.post(reverse('create_project'), {
            'name': 'New Project',
            'description': 'New Project Description'
        })
        assert response.status_code == 302
        assert Project.objects.filter(name='New Project').exists()

    def test_create_project_as_non_admin_forbidden(self):
        self.client.login(username='user', password='userpass123')
        response = self.client.post(reverse('create_project'), {
            'name': 'New Project',
            'description': 'New Project Description'
        })
        assert response.status_code == 403

    def test_project_issues_list_view(self):
        issue = Issue.objects.create(
            title="Test Issue",
            description="Test Description",
            project=self.project,
            author=self.user
        )
        response = self.client.get(reverse('project_issues_list', kwargs={'pk': self.project.pk}))
        assert response.status_code == 200
        assert issue.title.encode() in response.content
