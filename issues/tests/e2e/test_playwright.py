import pytest
import os
from playwright.sync_api import Page, expect
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.contrib.auth import get_user_model
from issues.models import Project, Issue, Comment
from django.test import TransactionTestCase

# Allow unsafe async operations in Django for Playwright tests
os.environ.setdefault('DJANGO_ALLOW_ASYNC_UNSAFE', '1')

User = get_user_model()

# -------------------------------
# HELPERS
# -------------------------------
def create_user(username, password, role="reporter"):
    """Create a user with the specified role."""
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password=password,
        role=role
    )

def create_project(name="Test Project"):
    """Create a project with the given name."""
    return Project.objects.create(
        name=name,
        description=f"Description for {name}"
    )

def create_issue(project, author, title="Bug #1", description="Bug description"):
    """Create an issue for the given project and author."""
    return Issue.objects.create(
        title=title,
        description=description,
        project=project,
        author=author,
        status="open"
    )

def project_exists(name):
    """Check if a project with the given name exists."""
    return Project.objects.filter(name=name).exists()

def issue_exists(title):
    """Check if an issue with the given title exists."""
    return Issue.objects.filter(title=title).exists()

def comment_exists(issue, text, author):
    """Check if a comment exists for the given issue."""
    return Comment.objects.filter(issue=issue, text=text, author=author).exists()

# -------------------------------
# FIXTURES
# -------------------------------
@pytest.fixture
def admin_user():
    return create_user("admin", "password123", "admin")

@pytest.fixture
def assignee_user():
    return create_user("assignee", "password123", "assignee")

@pytest.fixture
def reporter_user():
    return create_user("reporter", "password123", "reporter")

@pytest.fixture
def test_project(admin_user):
    return create_project("E2E Test Project")

@pytest.fixture
def test_issue(test_project, admin_user):
    return create_issue(test_project, admin_user, "E2E Test Issue", "Issue for testing")

# -------------------------------
# AUTH TESTS
# -------------------------------
@pytest.mark.django_db(transaction=True)
def test_login_with_valid_credentials(page: Page, live_server, admin_user):
    page.goto(f"{live_server.url}/login/")
    
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    expect(page).to_have_url(f"{live_server.url}/")
    expect(page.locator("text=Welcome")).to_be_visible()

@pytest.mark.django_db(transaction=True)
def test_login_with_invalid_credentials(page: Page, live_server):
    page.goto(f"{live_server.url}/login/")
    
    page.get_by_test_id("login-username").fill("invalid")
    page.get_by_test_id("login-password").fill("wrong")
    page.get_by_test_id("login-submit").click()
    
    expect(page.locator(".alert-error")).to_be_visible()

@pytest.mark.django_db(transaction=True)
def test_register_new_user(page: Page, live_server):
    page.goto(f"{live_server.url}/register/")
    
    page.get_by_test_id("register-username").fill("newuser")
    page.get_by_test_id("register-email").fill("newuser@example.com")
    page.get_by_test_id("register-password1").fill("testpass123")
    page.get_by_test_id("register-password2").fill("testpass123")
    page.get_by_test_id("register-submit").click()
    
    expect(page).to_have_url(f"{live_server.url}/")

# -------------------------------
# PROJECT CREATION
# -------------------------------
@pytest.mark.django_db(transaction=True)
def test_admin_can_create_project(page: Page, live_server, admin_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    page.get_by_test_id("add-project-link").click()
    expect(page).to_have_url(f"{live_server.url}/projects/create/")
    
    page.get_by_test_id("project-name").fill("New Project")
    page.get_by_test_id("project-description").fill("Project description")
    page.get_by_test_id("project-submit").click()
    
    expect(page).to_have_url(f"{live_server.url}/")
    assert project_exists("New Project")

@pytest.mark.django_db(transaction=True)
def test_reporter_cannot_see_add_project_link(page: Page, live_server, reporter_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill("reporter")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    expect(page.get_by_test_id("add-project-link")).not_to_be_visible()

@pytest.mark.django_db(transaction=True)
def test_project_creation_form_validation(page: Page, live_server, admin_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    page.get_by_test_id("add-project-link").click()
    page.get_by_test_id("project-submit").click()  # Submit without filling fields
    
    expect(page.get_by_test_id("project-name-error")).to_be_visible()

# -------------------------------
# ISSUE CREATION
# -------------------------------
@pytest.mark.django_db(transaction=True)
def test_authenticated_user_can_create_issue(page: Page, live_server, test_project, admin_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    
    expect(page.get_by_test_id("issue-form-container")).to_be_visible()
    page.get_by_test_id("issue-title").fill("New Issue")
    page.get_by_test_id("issue-description").fill("Issue description")
    page.get_by_test_id("issue-submit").click()
    
    page.wait_for_timeout(1000)  # Wait for HTMX
    expect(page.get_by_test_id("issue-item")).to_be_visible()
    assert issue_exists("New Issue")

@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("role", ["admin", "assignee", "reporter"])
def test_all_roles_can_create_issues(page: Page, live_server, test_project, role):
    user = create_user(f"user_{role}", "password123", role)
    
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill(f"user_{role}")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    
    page.get_by_test_id("issue-title").fill(f"Issue by {role}")
    page.get_by_test_id("issue-description").fill("Description")
    page.get_by_test_id("issue-submit").click()
    
    page.wait_for_timeout(1000)
    assert issue_exists(f"Issue by {role}")

@pytest.mark.django_db(transaction=True)
def test_anonymous_user_cannot_create_issue(page: Page, live_server, test_project):
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    
    expect(page.get_by_test_id("issue-form-container")).not_to_be_visible()
    expect(page.locator("text=You must")).to_be_visible()
    expect(page.locator("text=log in")).to_be_visible()

# -------------------------------
# STATUS CHANGE
# -------------------------------
@pytest.mark.django_db(transaction=True)
def test_admin_can_change_issue_status(page: Page, live_server, test_project, test_issue, admin_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    
    page.locator(f"select[name='status']").first.select_option("in_progress")
    page.wait_for_timeout(1000)  # Wait for HTMX
    
    test_issue.refresh_from_db()
    assert test_issue.status == "in_progress"

@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("role", ["admin", "assignee"])
def test_privileged_users_can_change_status(page: Page, live_server, test_project, test_issue, role):
    user = create_user(f"user_{role}", "password123", role)
    
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill(f"user_{role}")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    
    expect(page.locator("select[name='status']")).to_be_visible()

@pytest.mark.django_db(transaction=True)
def test_reporter_cannot_change_status(page: Page, live_server, test_project, test_issue, reporter_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill("reporter")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    
    expect(page.locator("select[name='status']")).not_to_be_visible()

# -------------------------------
# COMMENTS & HTMX
# -------------------------------
@pytest.mark.django_db(transaction=True)
def test_admin_can_add_comment(page: Page, live_server, test_project, test_issue, admin_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    
    # Open comments section
    page.locator(f"#toggle-comments-{test_issue.pk}").click()
    
    # Add comment
    page.locator(f"textarea[name='content']").fill("Test comment")
    page.locator("button[type='submit']").click()
    
    page.wait_for_timeout(1000)  # Wait for HTMX
    expect(page.get_by_test_id("comment-item")).to_be_visible()
    assert comment_exists(test_issue, "Test comment", admin_user)

@pytest.mark.django_db(transaction=True)
def test_comment_count_updates_with_htmx(page: Page, live_server, test_project, test_issue, admin_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    
    # Check initial count
    expect(page.locator(f"#comment-count-{test_issue.pk}")).to_contain_text("0")
    
    # Open comments and add one
    page.locator(f"#toggle-comments-{test_issue.pk}").click()
    page.locator(f"textarea[name='content']").fill("Test comment")
    page.locator("button[type='submit']").click()
    
    page.wait_for_timeout(1000)
    expect(page.locator(f"#comment-count-{test_issue.pk}")).to_contain_text("1")

@pytest.mark.django_db(transaction=True)
def test_reporter_cannot_add_comments(page: Page, live_server, test_project, test_issue, reporter_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill("reporter")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    
    page.locator(f"#toggle-comments-{test_issue.pk}").click()
    expect(page.locator("textarea[name='content']")).not_to_be_visible()

@pytest.mark.django_db(transaction=True)
def test_form_validation_on_empty_comment(page: Page, live_server, test_project, test_issue, admin_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    
    page.locator(f"#toggle-comments-{test_issue.pk}").click()
    page.locator("button[type='submit']").click()  # Submit empty form
    
    # Browser validation should prevent submission
    expect(page.locator("textarea[name='content']:invalid")).to_be_visible()

@pytest.mark.django_db(transaction=True)
def test_issue_list_updates_after_creation(page: Page, live_server, test_project, admin_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    
    # Check initial state
    initial_issues = page.get_by_test_id("issue-item").count()
    
    # Create new issue
    page.get_by_test_id("issue-title").fill("HTMX Test Issue")
    page.get_by_test_id("issue-description").fill("Testing HTMX updates")
    page.get_by_test_id("issue-submit").click()
    
    page.wait_for_timeout(1000)
    
    # Check that list updated
    new_count = page.get_by_test_id("issue-item").count()
    assert new_count == initial_issues + 1
    expect(page.locator("text=HTMX Test Issue")).to_be_visible()

@pytest.mark.django_db(transaction=True)
def test_no_issues_message_when_empty(page: Page, live_server, admin_user):
    empty_project = create_project("Empty Project")
    
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    page.goto(f"{live_server.url}/projects/{empty_project.pk}/")
    
    expect(page.get_by_test_id("no-issues")).to_be_visible()
    expect(page.locator("text=No issues yet")).to_be_visible()
