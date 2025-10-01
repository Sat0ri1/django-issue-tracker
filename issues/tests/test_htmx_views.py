import pytest
from django.test import Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from issues.models import Project, Issue, Comment

User = get_user_model()

@pytest.mark.django_db
class TestHTMXViews:
    def setup_method(self):
        self.client = Client()
        self.assignee_user = User.objects.create_user(
            username="assignee",
            email="assignee@example.com",
            password="assigneepass123",
            role="assignee"
        )
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            role="admin"
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

    def test_add_comment_htmx_request(self):
        issue = Issue.objects.create(
            title="Test Issue",
            description="Test Description",
            project=self.project,
            author=self.user
        )
        self.client.login(username='assignee', password='assigneepass123')
        
        response = self.client.post(
            reverse('add_comment', kwargs={'issue_pk': issue.pk}),
            {'content': 'HTMX comment'},
            HTTP_HX_REQUEST='true'
        )
        
        assert response.status_code == 200
        assert Comment.objects.filter(text='HTMX comment').exists()
        
        # Check response contains comment HTML
        assert b'HTMX comment' in response.content
        assert b'comment-item' in response.content
        
        # Check for OOB updates (licznik i usunięcie "No comments")
        assert b'hx-swap-oob' in response.content
        assert f'comment-count-{issue.pk}'.encode() in response.content

    def test_add_comment_htmx_updates_counter(self):
        issue = Issue.objects.create(
            title="Test Issue",
            description="Test Description",
            project=self.project,
            author=self.user
        )
        self.client.login(username='assignee', password='assigneepass123')
        
        # First comment
        response = self.client.post(
            reverse('add_comment', kwargs={'issue_pk': issue.pk}),
            {'content': 'First comment'},
            HTTP_HX_REQUEST='true'
        )
        
        assert response.status_code == 200
        # Should contain counter update with value 1
        assert b'comment-count-' in response.content
        assert b'>1<' in response.content or b'">1<' in response.content

    def test_add_comment_htmx_removes_no_comments_placeholder(self):
        issue = Issue.objects.create(
            title="Test Issue",
            description="Test Description",
            project=self.project,
            author=self.user
        )
        self.client.login(username='assignee', password='assigneepass123')
        
        response = self.client.post(
            reverse('add_comment', kwargs={'issue_pk': issue.pk}),
            {'content': 'First comment'},
            HTTP_HX_REQUEST='true'
        )
        
        assert response.status_code == 200
        # Should remove "No comments" placeholder on first comment
        assert f'no-comments-{issue.pk}'.encode() in response.content
        assert b'hx-swap-oob="true"' in response.content

    def test_add_comment_htmx_form_replacement(self):
        issue = Issue.objects.create(
            title="Test Issue",
            description="Test Description",
            project=self.project,
            author=self.user
        )
        self.client.login(username='assignee', password='assigneepass123')
        
        response = self.client.post(
            reverse('add_comment', kwargs={'issue_pk': issue.pk}),
            {'content': 'Test comment'},
            HTTP_HX_REQUEST='true'
        )
        
        assert response.status_code == 200
        # Should contain form replacement for clearing
        assert f'comment-form-{issue.pk}'.encode() in response.content
        assert b'placeholder="Write your comment..."' in response.content or b'placeholder="Napisz komentarz..."' in response.content

    def test_add_empty_comment_htmx(self):
        issue = Issue.objects.create(
            title="Test Issue",
            description="Test Description",
            project=self.project,
            author=self.user
        )
        self.client.login(username='assignee', password='assigneepass123')
        
        response = self.client.post(
            reverse('add_comment', kwargs={'issue_pk': issue.pk}),
            {'content': '   '},  # Empty or whitespace
            HTTP_HX_REQUEST='true'
        )
        
        assert response.status_code == 204  # No content
        assert not Comment.objects.filter(issue=issue).exists()

    def test_create_issue_htmx_request(self):
        self.client.login(username='user', password='userpass123')
        
        response = self.client.post(
            reverse('create_issue', kwargs={'project_pk': self.project.pk}),
            {
                'title': 'HTMX Issue',
                'description': 'HTMX Description',
                'priority': 'high'
            },
            HTTP_HX_REQUEST='true'
        )
        
        # Should return clean form with trigger header
        assert response.status_code == 200
        assert 'HX-Trigger' in response.headers
        assert Issue.objects.filter(title='HTMX Issue').exists()

    def test_change_status_htmx_request(self):
        issue = Issue.objects.create(
            title="Test Issue",
            description="Test Description",
            project=self.project,
            author=self.user,
            status="open"
        )
        self.client.login(username='assignee', password='assigneepass123')
        
        response = self.client.post(
            reverse('change_status', kwargs={'pk': issue.pk}),
            {'status': 'resolved'},
            HTTP_HX_REQUEST='true'
        )
        
        assert response.status_code == 200
        issue.refresh_from_db()
        assert issue.status == 'resolved'
        # Should return status badge
        assert b'status-badge' in response.content or b'resolved' in response.content.lower()

    def test_project_issues_list_htmx(self):
        issue = Issue.objects.create(
            title="Test Issue",
            description="Test Description",
            project=self.project,
            author=self.user
        )
        
        response = self.client.get(
            reverse('project_issues_list', kwargs={'pk': self.project.pk}),
            HTTP_HX_REQUEST='true'
        )
        
        assert response.status_code == 200
        assert issue.title.encode() in response.content
        # Should return partial template
        assert b'<!DOCTYPE html>' not in response.content  # Not full page
