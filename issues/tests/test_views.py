from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from issues.models import Project, Issue, Comment

User = get_user_model()


class ProjectViewsTest(TestCase):
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

    def test_project_list_view(self):
        """Test project list displays all projects"""
        response = self.client.get(reverse("project_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Project")
        self.assertContains(response, 'data-testid="project-item"')

    def test_project_detail_view(self):
        """Test project detail view displays project info and forms"""
        response = self.client.get(reverse("project_detail", kwargs={"pk": self.project.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TEST PROJECT")  # uppercase in template
        self.assertContains(response, 'data-testid="issues-list-wrapper"')

    def test_project_detail_authenticated_user_sees_form(self):
        """Test that authenticated users see the issue form"""
        self.client.login(username="user", password="testpass123")
        response = self.client.get(reverse("project_detail", kwargs={"pk": self.project.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-testid="issue-form-container"')
        self.assertContains(response, 'data-testid="issue-form"')

    def test_project_detail_unauthenticated_user_no_form(self):
        """Test that unauthenticated users don't see the issue form"""
        response = self.client.get(reverse("project_detail", kwargs={"pk": self.project.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'data-testid="issue-form"')
        self.assertContains(response, "log in")

    def test_project_issues_list_endpoint(self):
        """Test the dedicated issues list endpoint"""
        response = self.client.get(reverse("project_issues_list", kwargs={"pk": self.project.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-testid="issues-list"')


class IssueViewsTest(TestCase):
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

    def test_issue_detail_view(self):
        """Test issue detail view displays issue info"""
        response = self.client.get(reverse("issue_detail", kwargs={"pk": self.issue.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Issue")
        self.assertContains(response, "Test Description")
        self.assertContains(response, 'data-testid="issue-container"')

    def test_issue_detail_comments_section(self):
        """Test issue detail includes comments section"""
        response = self.client.get(reverse("issue_detail", kwargs={"pk": self.issue.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-testid="comments-section"')
        self.assertContains(response, 'data-testid="comments-list"')

    def test_create_issue_authenticated(self):
        """Test creating issue when authenticated"""
        self.client.login(username="user", password="testpass123")
        response = self.client.post(
            reverse("create_issue", kwargs={"project_pk": self.project.pk}),
            {"title": "New Issue", "description": "New Description"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Issue.objects.filter(title="New Issue").exists())

    def test_create_issue_htmx_success(self):
        """Test creating issue via HTMX returns clean form"""
        self.client.login(username="user", password="testpass123")
        response = self.client.post(
            reverse("create_issue", kwargs={"project_pk": self.project.pk}),
            {"title": "HTMX Issue", "description": "HTMX Description"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-testid="issue-form-container"')
        self.assertContains(response, "Add New Issue")
        self.assertEqual(response.get("HX-Trigger"), "issueCreated")

    def test_create_issue_htmx_validation_error(self):
        """Test creating issue via HTMX with validation errors"""
        self.client.login(username="user", password="testpass123")
        response = self.client.post(
            reverse("create_issue", kwargs={"project_pk": self.project.pk}),
            {"title": "", "description": "No title"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-testid="issue-form-container"')

    def test_create_issue_unauthenticated(self):
        """Test creating issue when unauthenticated redirects to login"""
        response = self.client.post(
            reverse("create_issue", kwargs={"project_pk": self.project.pk}),
            {"title": "Unauthorized Issue", "description": "Should not work"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)


class CommentViewsTest(TestCase):
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

    def test_add_comment_assignee(self):
        """Test assignee can add comments"""
        self.client.login(username="assignee", password="testpass123")
        response = self.client.post(
            reverse("add_comment", kwargs={"issue_pk": self.issue.pk}),
            {"text": "Test comment"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Comment.objects.filter(text="Test comment").exists())

    def test_add_comment_admin(self):
        """Test admin can add comments"""
        self.client.login(username="admin", password="testpass123")
        response = self.client.post(
            reverse("add_comment", kwargs={"issue_pk": self.issue.pk}),
            {"text": "Admin comment"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Comment.objects.filter(text="Admin comment").exists())

    def test_add_comment_regular_user_forbidden(self):
        """Test regular user cannot add comments"""
        self.client.login(username="user", password="testpass123")
        response = self.client.post(
            reverse("add_comment", kwargs={"issue_pk": self.issue.pk}),
            {"text": "Should not work"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Comment.objects.filter(text="Should not work").exists())

    def test_add_comment_htmx_success(self):
        """Test adding comment via HTMX returns updated comments section"""
        self.client.login(username="assignee", password="testpass123")
        response = self.client.post(
            reverse("add_comment", kwargs={"issue_pk": self.issue.pk}),
            {"text": "HTMX comment"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-testid="comments-section"')
        self.assertContains(response, 'data-testid="comment-form"')
        self.assertContains(response, "Write your comment...")

    def test_add_comment_htmx_validation_error(self):
        """Test adding comment via HTMX with validation errors"""
        self.client.login(username="assignee", password="testpass123")
        response = self.client.post(
            reverse("add_comment", kwargs={"issue_pk": self.issue.pk}),
            {"text": ""},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-testid="comments-section"')


class StatusChangeViewsTest(TestCase):
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

    def test_change_status_assignee(self):
        """Test assignee can change issue status"""
        self.client.login(username="assignee", password="testpass123")
        response = self.client.post(
            reverse("change_status", kwargs={"pk": self.issue.pk}),
            {"status": "in_progress"},
        )
        self.assertEqual(response.status_code, 302)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, "in_progress")

    def test_change_status_admin(self):
        """Test admin can change issue status"""
        self.client.login(username="admin", password="testpass123")
        response = self.client.post(
            reverse("change_status", kwargs={"pk": self.issue.pk}),
            {"status": "resolved"},
        )
        self.assertEqual(response.status_code, 302)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, "resolved")

    def test_change_status_regular_user_forbidden(self):
        """Test regular user cannot change issue status"""
        self.client.login(username="user", password="testpass123")
        response = self.client.post(
            reverse("change_status", kwargs={"pk": self.issue.pk}),
            {"status": "resolved"},
        )
        self.assertEqual(response.status_code, 403)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, "open")
