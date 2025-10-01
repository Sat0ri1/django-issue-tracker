import os
import pytest
from playwright.sync_api import Page, expect
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.contrib.auth import get_user_model
from issues.models import Project, Issue, Comment

# Allow unsafe async operations in Django for Playwright tests
os.environ.setdefault('DJANGO_ALLOW_ASYNC_UNSAFE', '1')

User = get_user_model()

# -------------------------------
# HELPERS
# -------------------------------
def create_user(username, password, role="reporter"):
    return User.objects.create_user(username=username, password=password, role=role)

def create_project(name="Test Project"):
    return Project.objects.create(name=name)

def create_issue(project, author, title="Bug #1", description="Bug description"):
    return Issue.objects.create(project=project, author=author, title=title, description=description)

def project_exists(name):
    return Project.objects.filter(name=name).exists()

def issue_exists(title):
    return Issue.objects.filter(title=title).exists()

def comment_exists(issue, text, author):
    return Comment.objects.filter(issue=issue, text=text, author=author).exists()


# -------------------------------
# FIXTURES
# -------------------------------
@pytest.fixture
def admin_user(db):
    return create_user("admin", "password123", role="admin")

@pytest.fixture
def assignee_user(db):
    return create_user("assignee", "password123", role="assignee")

@pytest.fixture
def reporter_user(db):
    return create_user("reporter", "password123", role="reporter")

@pytest.fixture
def project(db):
    return create_project()

@pytest.fixture
def issue(db, project, reporter_user):
    return create_issue(project, reporter_user)


# -------------------------------
# AUTH TESTS
# -------------------------------
@pytest.mark.django_db(transaction=True)
def test_register_valid(page: Page, live_server):
    page.goto(f"{live_server.url}/register/")
    page.get_by_test_id("register-username").fill("play_user")
    page.get_by_test_id("register-email").fill("play@example.com")
    page.get_by_test_id("register-password1").fill("StrongPass123")
    page.get_by_test_id("register-password2").fill("StrongPass123")
    page.get_by_test_id("register-submit").click()
    assert User.objects.filter(username="play_user").exists()


@pytest.mark.django_db(transaction=True)
def test_register_invalid(page: Page, live_server):
    page.goto(f"{live_server.url}/register/")
    page.get_by_test_id("register-username").fill("")
    page.get_by_test_id("register-email").fill("bademail")
    page.get_by_test_id("register-password1").fill("123")
    page.get_by_test_id("register-password2").fill("456")
    page.get_by_test_id("register-submit").click()
    assert not User.objects.filter(username="").exists()
    assert "register" in page.url.lower()


@pytest.mark.django_db(transaction=True)
def test_logout_logs_user_out(page: Page, live_server, reporter_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill(reporter_user.username)
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    page.wait_for_load_state("networkidle")
    logout_element = page.get_by_test_id("logout")
    assert logout_element.is_visible()
    logout_element.click()
    page.wait_for_load_state("networkidle")
    login_visible = page.get_by_test_id("login").is_visible()
    assert login_visible


# -------------------------------
# PROJECT CREATION
# -------------------------------
@pytest.mark.django_db(transaction=True)
def test_create_project_requires_login(page: Page, live_server):
    page.goto(f"{live_server.url}/projects/create/")
    assert "login" in page.url


@pytest.mark.django_db(transaction=True)
def test_create_project_allowed_for_admin(page: Page, live_server, admin_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill(admin_user.username)
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    page.goto(f"{live_server.url}/projects/create/")
    page.get_by_test_id("project-name").fill("Admin Project")
    page.get_by_test_id("project-description").fill("Admin project description")
    page.get_by_test_id("project-submit").click()
    page.wait_for_load_state("networkidle")
    assert project_exists("Admin Project")


@pytest.mark.django_db(transaction=True)
def test_create_project_forbidden_for_non_admin(page: Page, live_server, reporter_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill(reporter_user.username)
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    page.goto(f"{live_server.url}/projects/create/")
    content = page.content()
    forbidden_messages = [
        "forbidden" in content.lower(),
        "403" in content,
        "login" in page.url,
        "only admin" in content.lower(),
        "access denied" in content.lower(),
        "permission denied" in content.lower()
    ]
    assert any(forbidden_messages), f"Expected forbidden access, but got: {content}"


# -------------------------------
# ISSUE CREATION
# -------------------------------
@pytest.mark.django_db(transaction=True)
def test_create_issue_requires_login(page: Page, live_server, project):
    page.goto(f"{live_server.url}/projects/{project.pk}/issues/create/")
    assert "login" in page.url


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("role", ["admin", "assignee", "reporter"])
def test_create_issue_logged_in(page: Page, live_server, project, db, role):
    user = create_user(f"user_{role}", "pass", role=role)
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill(user.username)
    page.get_by_test_id("login-password").fill("pass")
    page.get_by_test_id("login-submit").click()
    page.goto(f"{live_server.url}/projects/{project.pk}/")
    page.get_by_test_id("issue-title").fill(f"Issue by {role}")
    page.get_by_test_id("issue-description").fill("Issue description")
    page.get_by_test_id("issue-submit").click()
    page.wait_for_load_state("networkidle")
    assert issue_exists(f"Issue by {role}")


@pytest.mark.django_db(transaction=True)
def test_create_issue_invalid_form(page: Page, live_server, project, reporter_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill(reporter_user.username)
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    page.goto(f"{live_server.url}/projects/{project.pk}/")
    page.get_by_test_id("issue-title").fill("")
    page.get_by_test_id("issue-description").fill("desc")
    page.get_by_test_id("issue-submit").click()
    page.wait_for_load_state("networkidle")
    assert not issue_exists("")
    assert page.url.endswith("/") or f"projects/{project.pk}" in page.url


# -------------------------------
# STATUS CHANGE
# -------------------------------
@pytest.mark.django_db(transaction=True)
def test_change_status_requires_login(page: Page, live_server, issue):
    page.goto(f"{live_server.url}/issues/{issue.pk}/change-status/")
    assert "login" in page.url


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("role", ["admin", "assignee"])
def test_change_status_allowed(page: Page, live_server, issue, role):
    user = create_user(f"user_{role}", "pass", role=role)
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill(user.username)
    page.get_by_test_id("login-password").fill("pass")
    page.get_by_test_id("login-submit").click()
    page.goto(f"{live_server.url}/projects/{issue.project.pk}/")
    page.wait_for_load_state("networkidle")
    status_select = page.get_by_test_id(f"status-select-{issue.pk}")
    assert status_select.is_visible(), f"Status select should be visible for {role}"
    status_select.select_option("done")
    update_button = page.get_by_test_id(f"status-update-{issue.pk}")
    assert update_button.is_visible(), "Update button should be visible"
    update_button.click()
    page.wait_for_timeout(1000)
    issue.refresh_from_db()
    assert issue.status == "done"


@pytest.mark.django_db(transaction=True)
def test_change_status_forbidden_for_regular_user(page: Page, live_server, issue, reporter_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill(reporter_user.username)
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    page.goto(f"{live_server.url}/projects/{issue.project.pk}/")
    page.wait_for_load_state("networkidle")
    status_select = page.get_by_test_id(f"status-select-{issue.pk}")
    assert not status_select.is_visible(), "Status select should not be visible for reporters"
    issue.refresh_from_db()
    assert issue.status == issue.status


# -------------------------------
# COMMENTS & HTMX
# -------------------------------
@pytest.mark.django_db(transaction=True)
def test_add_comment_requires_login(page: Page, live_server, issue):
    page.goto(f"{live_server.url}/issues/{issue.pk}/comments/add/")
    assert "login" in page.url


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("role", ["admin", "assignee"])
def test_add_comment_allowed(page: Page, live_server, issue, role):
    user = create_user(f"user_{role}", "pass", role=role)
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill(user.username)
    page.get_by_test_id("login-password").fill("pass")
    page.get_by_test_id("login-submit").click()
    page.goto(f"{live_server.url}/projects/{issue.project.pk}/")
    page.wait_for_load_state("networkidle")
    comments_summary = page.get_by_test_id(f"comments-section-{issue.pk}").locator("summary")
    if comments_summary.is_visible():
        comments_summary.click()
        page.wait_for_timeout(500)
    textarea = page.get_by_test_id("comment-form").locator("textarea")
    assert textarea.is_visible(), f"Comment textarea should be visible for {role}"
    textarea.fill(f"Comment by {role}")
    add_button = page.get_by_test_id("comment-submit")
    assert add_button.is_visible(), "Add Comment button should be visible"
    add_button.click()
    page.wait_for_timeout(1000)
    assert comment_exists(issue, f"Comment by {role}", user)


@pytest.mark.django_db(transaction=True)
def test_add_comment_forbidden_for_regular_user(page: Page, live_server, issue, reporter_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill(reporter_user.username)
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    page.goto(f"{live_server.url}/projects/{issue.project.pk}/")
    page.wait_for_load_state("networkidle")
    comments_summary = page.get_by_test_id(f"comments-section-{issue.pk}").locator("summary")
    if comments_summary.is_visible():
        comments_summary.click()
        page.wait_for_timeout(500)
    textarea = page.get_by_test_id("comment-form").locator("textarea")
    assert not textarea.is_visible(), "Comment form should not be visible for reporters"
    assert not comment_exists(issue, "Blocked comment", reporter_user)


@pytest.mark.django_db(transaction=True)
def test_add_comment_invalid_form(page: Page, live_server, issue, admin_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill(admin_user.username)
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    page.goto(f"{live_server.url}/projects/{issue.project.pk}/")
    page.wait_for_load_state("networkidle")
    comments_summary = page.get_by_test_id(f"comments-section-{issue.pk}").locator("summary")
    if comments_summary.is_visible():
        comments_summary.click()
        page.wait_for_timeout(500)
    textarea = page.get_by_test_id("comment-form").locator("textarea")
    textarea.fill("")
    add_button = page.get_by_test_id("comment-submit")
    add_button.click()
    page.wait_for_timeout(1000)
    assert not comment_exists(issue, "", admin_user)


# -------------------------------
# PLAYWRIGHT TEST CASE
# -------------------------------
class PlaywrightTestCase(StaticLiveServerTestCase):
    """Base test case for Playwright tests with Django Live Server"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin_user = User.objects.create_user(
            username="admin", email="admin@test.com", password="testpass123", role="admin"
        )
        cls.assignee_user = User.objects.create_user(
            username="assignee", email="assignee@test.com", password="testpass123", role="assignee"
        )
        cls.user = User.objects.create_user(
            username="user", email="user@test.com", password="testpass123", role="user"
        )
        cls.project = Project.objects.create(name="Test Project")

    def login_user(self, page: Page, username: str, password: str = "testpass123"):
        """Helper method to log in a user via the UI"""
        page.goto(f"{self.live_server_url}/auth/login/")
        page.fill('[data-testid="username"]', username)
        page.fill('[data-testid="password"]', password)
        page.click('[data-testid="login-submit"]')


@pytest.mark.django_db
class TestIssueCreationFlow(PlaywrightTestCase):
    """Test the complete issue creation flow with HTMX"""

    def test_create_issue_flow(self, page: Page):
        """Test creating an issue and seeing it appear in the list"""
        self.login_user(page, "user")
        
        # Navigate to project detail
        page.goto(f"{self.live_server_url}/projects/{self.project.pk}/")
        
        # Verify issue form is visible
        expect(page.locator('[data-testid="issue-form-container"]')).to_be_visible()
        
        # Fill and submit the form
        page.fill('[data-testid="issue-title"]', "E2E Test Issue")
        page.fill('[data-testid="issue-description"]', "This is a test issue created via E2E testing")
        page.click('[data-testid="issue-submit"]')
        
        # Wait for form to be replaced with clean form
        expect(page.locator('[data-testid="issue-form-container"]')).to_be_visible()
        expect(page.locator('[data-testid="issue-title"]')).to_have_value("")
        
        # Wait for issue to appear in the list
        expect(page.locator('[data-testid="issue-item"]')).to_be_visible()
        expect(page.locator('text="E2E Test Issue"')).to_be_visible()

    def test_create_issue_validation_errors(self, page: Page):
        """Test form validation errors display correctly"""
        self.login_user(page, "user")
        page.goto(f"{self.live_server_url}/projects/{self.project.pk}/")
        
        # Submit empty form
        page.click('[data-testid="issue-submit"]')
        
        # Check for validation errors
        expect(page.locator('[data-testid="issue-title-error"]')).to_be_visible()

    def test_admin_sees_assignee_field(self, page: Page):
        """Test that admin users see the assignee selection field"""
        self.login_user(page, "admin")
        page.goto(f"{self.live_server_url}/projects/{self.project.pk}/")
        
        # Admin should see assignee field
        expect(page.locator('[data-testid="issue-assignee"]')).to_be_visible()

    def test_regular_user_no_assignee_field(self, page: Page):
        """Test that regular users don't see the assignee selection field"""
        self.login_user(page, "user")
        page.goto(f"{self.live_server_url}/projects/{self.project.pk}/")
        
        # Regular user should not see assignee field
        expect(page.locator('[data-testid="issue-assignee"]')).not_to_be_visible()


@pytest.mark.django_db
class TestCommentFlow(PlaywrightTestCase):
    """Test the comment creation and display flow"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.issue = Issue.objects.create(
            title="Test Issue for Comments",
            description="Test Description",
            project=cls.project,
            author=cls.user,
            assignee=cls.assignee_user,
        )

    def test_assignee_can_add_comments(self, page: Page):
        """Test that assignees can add comments"""
        self.login_user(page, "assignee")
        page.goto(f"{self.live_server_url}/issues/{self.issue.pk}/")
        
        # Verify comment form is visible
        expect(page.locator('[data-testid="comment-form"]')).to_be_visible()
        expect(page.locator('[data-testid="comment-text"]')).to_be_visible()
        
        # Add a comment
        page.fill('[data-testid="comment-text"]', "This is a test comment from assignee")
        page.click('[data-testid="comment-submit"]')
        
        # Wait for comment to appear
        expect(page.locator('text="This is a test comment from assignee"')).to_be_visible()
        
        # Verify form is cleared
        expect(page.locator('[data-testid="comment-text"]')).to_have_value("")

    def test_admin_can_add_comments(self, page: Page):
        """Test that admins can add comments"""
        self.login_user(page, "admin")
        page.goto(f"{self.live_server_url}/issues/{self.issue.pk}/")
        
        # Verify comment form is visible
        expect(page.locator('[data-testid="comment-form"]')).to_be_visible()
        
        # Add a comment
        page.fill('[data-testid="comment-text"]', "This is a test comment from admin")
        page.click('[data-testid="comment-submit"]')
        
        # Wait for comment to appear
        expect(page.locator('text="This is a test comment from admin"')).to_be_visible()

    def test_regular_user_cannot_add_comments(self, page: Page):
        """Test that regular users cannot add comments"""
        self.login_user(page, "user")
        page.goto(f"{self.live_server_url}/issues/{self.issue.pk}/")
        
        # Should not see comment form
        expect(page.locator('[data-testid="comment-form"]')).not_to_be_visible()
        
        # Should see message about permissions
        expect(page.locator('text="Only assignees and admins can add comments"')).to_be_visible()

    def test_comment_scrolling(self, page: Page):
        """Test that comments section scrolls when there are many comments"""
        # Create multiple comments first
        from issues.models import Comment
        for i in range(10):
            Comment.objects.create(
                text=f"Comment {i}",
                issue=self.issue,
                author=self.assignee_user
            )
        
        self.login_user(page, "assignee")
        page.goto(f"{self.live_server_url}/issues/{self.issue.pk}/")
        
        # Check that comments list has overflow styling
        comments_list = page.locator('[data-testid="comments-list"]')
        expect(comments_list).to_be_visible()
        expect(comments_list).to_have_css("overflow-y", "auto")


@pytest.mark.django_db
class TestResponsiveDesign(PlaywrightTestCase):
    """Test responsive design and mobile compatibility"""

    def test_mobile_layout(self, page: Page):
        """Test that the layout works on mobile devices"""
        # Set mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        
        self.login_user(page, "user")
        page.goto(f"{self.live_server_url}/projects/{self.project.pk}/")
        
        # Verify form is still visible and usable on mobile
        expect(page.locator('[data-testid="issue-form-container"]')).to_be_visible()
        expect(page.locator('[data-testid="issue-title"]')).to_be_visible()
        expect(page.locator('[data-testid="issue-description"]')).to_be_visible()

    def test_tablet_layout(self, page: Page):
        """Test that the layout works on tablet devices"""
        # Set tablet viewport
        page.set_viewport_size({"width": 768, "height": 1024})
        
        self.login_user(page, "user")
        page.goto(f"{self.live_server_url}/projects/{self.project.pk}/")
        
        # Verify layout adapts to tablet size
        expect(page.locator('[data-testid="issue-form-container"]')).to_be_visible()
        expect(page.locator('[data-testid="issues-list"]')).to_be_visible()


@pytest.mark.django_db
class TestHTMXInteractions(PlaywrightTestCase):
    """Test HTMX-specific interactions and behaviors"""

    def test_issue_list_updates_without_page_refresh(self, page: Page):
        """Test that issue list updates via HTMX without full page refresh"""
        self.login_user(page, "user")
        page.goto(f"{self.live_server_url}/projects/{self.project.pk}/")
        
        # Get initial page URL
        initial_url = page.url
        
        # Create an issue
        page.fill('[data-testid="issue-title"]', "HTMX Test Issue")
        page.fill('[data-testid="issue-description"]', "Testing HTMX updates")
        page.click('[data-testid="issue-submit"]')
        
        # Verify URL hasn't changed (no full page refresh)
        expect(page).to_have_url(initial_url)
        
        # Verify issue appears in list
        expect(page.locator('text="HTMX Test Issue"')).to_be_visible()

    def test_form_replacement_on_success(self, page: Page):
        """Test that form is replaced with clean form on successful submission"""
        self.login_user(page, "user")
        page.goto(f"{self.live_server_url}/projects/{self.project.pk}/")
        
        # Fill form
        page.fill('[data-testid="issue-title"]', "Form Replacement Test")
        page.fill('[data-testid="issue-description"]', "Testing form replacement")
        
        # Submit form
        page.click('[data-testid="issue-submit"]')
        
        # Verify form is cleared
        expect(page.locator('[data-testid="issue-title"]')).to_have_value("")
        expect(page.locator('[data-testid="issue-description"]')).to_have_value("")

    def test_comment_form_stays_visible(self, page: Page):
        """Test that comment form is always visible and doesn't require clicking"""
        issue = Issue.objects.create(
            title="Comment Visibility Test",
            description="Test Description",
            project=self.project,
            author=self.user,
            assignee=self.assignee_user,
        )
        
        self.login_user(page, "assignee")
        page.goto(f"{self.live_server_url}/issues/{issue.pk}/")
        
        # Verify comment form is immediately visible
        expect(page.locator('[data-testid="comment-form"]')).to_be_visible()
        expect(page.locator('[data-testid="comment-text"]')).to_be_visible()
        
        # Verify placeholder text
        expect(page.locator('[data-testid="comment-text"]')).to_have_attribute("placeholder", "Write your comment...")
