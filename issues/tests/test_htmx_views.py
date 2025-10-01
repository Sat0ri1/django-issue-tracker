from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from issues.models import Project, Issue, Comment

User = get_user_model()


class HTMXViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username="admin", email="admin@test.com", password="testpass123", role="admin"
        )
        self.assignee_user = User.objects.create_user(
            username="assignee", email="assignee@test.com", password="testpass123", role="assignee"
        )
        self.user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123", role="user"
        )
        self.project = Project.objects.create(name="Test Project")
        self.issue = Issue.objects.create(
            title="Test Issue",
            description="Test Description",
            project=self.project,
            author=self.user,
            assignee=self.assignee_user,
        )

    def test_htmx_create_issue_success(self):
        """Test HTMX issue creation returns clean form and triggers refresh"""
        self.client.login(username="user", password="testpass123")
        response = self.client.post(
            reverse("create_issue", kwargs={"project_pk": self.project.pk}),
            {"title": "HTMX Issue", "description": "HTMX Description"},
            HTTP_HX_REQUEST="true",
        )
        
        self.assertEqual(response.status_code, 200)
        # Check for clean form container
        self.assertContains(response, 'id="issue-form-container"')
        self.assertContains(response, 'data-testid="issue-form-container"')
        self.assertContains(response, 'data-testid="issue-form"')
        
        # Check for form fields
        self.assertContains(response, 'data-testid="issue-title"')
        self.assertContains(response, 'data-testid="issue-description"')
        self.assertContains(response, 'data-testid="issue-submit"')
        
        # Check for HX-Trigger header
        self.assertEqual(response.get("HX-Trigger"), "issueCreated")
        
        # Verify issue was created
        self.assertTrue(Issue.objects.filter(title="HTMX Issue").exists())

    def test_htmx_create_issue_validation_errors(self):
        """Test HTMX issue creation with validation errors"""
        self.client.login(username="user", password="testpass123")
        response = self.client.post(
            reverse("create_issue", kwargs={"project_pk": self.project.pk}),
            {"title": "", "description": "No title"},
            HTTP_HX_REQUEST="true",
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-testid="issue-form-container"')
        # Should contain error messages
        self.assertContains(response, 'data-testid="issue-title-error"')

    def test_htmx_add_comment_success(self):
        """Test HTMX comment addition returns updated comments section"""
        self.client.login(username="assignee", password="testpass123")
        response = self.client.post(
            reverse("add_comment", kwargs={"issue_pk": self.issue.pk}),
            {"text": "HTMX comment"},
            HTTP_HX_REQUEST="true",
        )
        
        self.assertEqual(response.status_code, 200)
        # Check for comments section structure
        self.assertContains(response, f'id="comments-section-{self.issue.pk}"')
        self.assertContains(response, 'data-testid="comments-section"')
        self.assertContains(response, 'data-testid="comments-list"')
        self.assertContains(response, 'data-testid="comment-form"')
        
        # Check for empty comment form (clean state)
        self.assertContains(response, 'data-testid="comment-text"')
        self.assertContains(response, 'data-testid="comment-submit"')
        self.assertContains(response, "Write your comment...")
        
        # Verify comment was created
        self.assertTrue(Comment.objects.filter(text="HTMX comment").exists())

    def test_htmx_add_comment_validation_errors(self):
        """Test HTMX comment addition with validation errors"""
        self.client.login(username="assignee", password="testpass123")
        response = self.client.post(
            reverse("add_comment", kwargs={"issue_pk": self.issue.pk}),
            {"text": ""},
            HTTP_HX_REQUEST="true",
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-testid="comments-section"')
        # Should contain error messages
        self.assertContains(response, 'data-testid="comment-error"')

    def test_htmx_change_status(self):
        """Test HTMX status change returns status badge"""
        self.client.login(username="assignee", password="testpass123")
        response = self.client.post(
            reverse("change_status", kwargs={"pk": self.issue.pk}),
            {"status": "in_progress"},
            HTTP_HX_REQUEST="true",
        )
        
        self.assertEqual(response.status_code, 200)
        # Verify it returns status badge template
        self.assertContains(response, "in_progress")

    def test_htmx_project_issues_list(self):
        """Test HTMX project issues list endpoint"""
        response = self.client.get(
            reverse("project_issues_list", kwargs={"pk": self.project.pk}),
            HTTP_HX_REQUEST="true",
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="issues-list"')
        self.assertContains(response, 'data-testid="issues-list"')
        # Should contain HTMX attributes for refresh
        self.assertContains(response, 'hx-get=')
        self.assertContains(response, 'hx-trigger="issueCreated from:body"')

    def test_htmx_issue_list_with_issues(self):
        """Test HTMX issues list displays issues correctly"""
        response = self.client.get(
            reverse("project_issues_list", kwargs={"pk": self.project.pk}),
            HTTP_HX_REQUEST="true",
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-testid="issue-item"')
        self.assertContains(response, "Test Issue")

    def test_htmx_issue_list_empty(self):
        """Test HTMX issues list displays empty state correctly"""
        # Remove existing issue
        self.issue.delete()
        
        response = self.client.get(
            reverse("project_issues_list", kwargs={"pk": self.project.pk}),
            HTTP_HX_REQUEST="true",
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-testid="no-issues"')
        self.assertContains(response, "No issues yet")

    def test_htmx_headers_detection(self):
        """Test that views properly detect HTMX requests"""
        self.client.login(username="user", password="testpass123")
        
        # Regular request
        response = self.client.post(
            reverse("create_issue", kwargs={"project_pk": self.project.pk}),
            {"title": "Regular Issue", "description": "Regular Description"},
        )
        self.assertEqual(response.status_code, 302)  # Redirect
        
        # HTMX request
        response = self.client.post(
            reverse("create_issue", kwargs={"project_pk": self.project.pk}),
            {"title": "HTMX Issue", "description": "HTMX Description"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)  # Template response

    def test_htmx_comments_section_permissions(self):
        """Test comments section shows appropriate content based on user role"""
        # Test as regular user
        self.client.login(username="user", password="testpass123")
        response = self.client.get(reverse("issue_detail", kwargs={"pk": self.issue.pk}))
        self.assertContains(response, "Only assignees and admins can add comments")
        
        # Test as assignee
        self.client.login(username="assignee", password="testpass123")
        response = self.client.get(reverse("issue_detail", kwargs={"pk": self.issue.pk}))
        self.assertContains(response, 'data-testid="comment-form"')
        self.assertContains(response, "Write your comment...")
        
        # Test as admin
        self.client.login(username="admin", password="testpass123")
        response = self.client.get(reverse("issue_detail", kwargs={"pk": self.issue.pk}))
        self.assertContains(response, 'data-testid="comment-form"')
        self.assertContains(response, "Write your comment...")

    def test_htmx_form_styling_consistency(self):
        """Test that HTMX forms maintain consistent styling"""
        self.client.login(username="user", password="testpass123")
        response = self.client.get(reverse("project_detail", kwargs={"pk": self.project.pk}))
        
        # Check for consistent styling classes
        self.assertContains(response, "bg-gray-700")
        self.assertContains(response, "bg-gray-600")
        self.assertContains(response, "rounded-lg")
        self.assertContains(response, "shadow-xl")
