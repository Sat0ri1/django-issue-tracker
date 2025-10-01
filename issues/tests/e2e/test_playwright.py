import pytest
import os
from playwright.sync_api import Page, expect
from django.contrib.auth import get_user_model
from issues.models import Project, Issue, Comment

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
        status="todo"
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
    user = User.objects.create_user(
        username="admin",
        email="admin@example.com", 
        password="password123",
        role="admin"
    )
    return user

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
# AUTH TESTS - UŻYWAMY TEST-IDS
# -------------------------------
@pytest.mark.django_db(transaction=True)
def test_login_with_valid_credentials(page: Page, live_server, admin_user):
    page.goto(f"{live_server.url}/login/")
    
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    expect(page).to_have_url(f"{live_server.url}/")

@pytest.mark.django_db(transaction=True)
def test_login_with_invalid_credentials(page: Page, live_server):
    page.goto(f"{live_server.url}/login/")
    
    page.get_by_test_id("login-username").fill("invalid")
    page.get_by_test_id("login-password").fill("wrong")
    page.get_by_test_id("login-submit").click()
    
    expect(page).to_have_url(f"{live_server.url}/login/")

@pytest.mark.django_db(transaction=True)
def test_register_new_user(page: Page, live_server):
    page.goto(f"{live_server.url}/register/")
    
    page.get_by_test_id("register-username").fill("newuser")
    page.get_by_test_id("register-email").fill("newuser@example.com")
    page.get_by_test_id("register-password1").fill("testpass123")
    page.get_by_test_id("register-password2").fill("testpass123")
    
    # Sprawdź czy pole role ma test-id
    role_select = page.get_by_test_id("register-role")
    if role_select.count() > 0:
        role_select.select_option("reporter")
    
    page.get_by_test_id("register-submit").click()
    expect(page).to_have_url(f"{live_server.url}/login/")

# -------------------------------
# PROJECT CREATION - UŻYWAMY TEST-IDS
# -------------------------------
@pytest.mark.django_db(transaction=True)
def test_admin_can_create_project(page: Page, live_server, admin_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    expect(page).to_have_url(f"{live_server.url}/")
    
    # Użyj test-id dla linku do tworzenia projektów
    create_project_link = page.get_by_test_id("create-project-link")
    expect(create_project_link).to_be_visible()
    create_project_link.click()
    
    expect(page).to_have_url(f"{live_server.url}/projects/create/")
    
    page.get_by_test_id("project-name").fill("Admin Test Project")
    page.get_by_test_id("project-description").fill("Project created by admin")
    page.get_by_test_id("project-submit").click()
    
    page.wait_for_timeout(2000)
    expect(page).to_have_url(f"{live_server.url}/")
    assert project_exists("Admin Test Project")

@pytest.mark.django_db(transaction=True)
def test_reporter_cannot_create_project(page: Page, live_server, reporter_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill("reporter")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    # Reporter nie powinien widzieć linku do tworzenia projektów
    expect(page.get_by_test_id("create-project-link")).not_to_be_visible()

@pytest.mark.django_db(transaction=True)
def test_assignee_cannot_create_project(page: Page, live_server, assignee_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill("assignee")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    expect(page.get_by_test_id("create-project-link")).not_to_be_visible()

# -------------------------------
# ISSUE CREATION - UŻYWAMY TEST-IDS
# -------------------------------
@pytest.mark.django_db(transaction=True)
def test_authenticated_user_can_create_issue(page: Page, live_server, test_project, admin_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    
    page.get_by_test_id("issue-title").fill("New Issue")
    page.get_by_test_id("issue-description").fill("Issue description")
    page.get_by_test_id("issue-submit").click()
    
    page.wait_for_timeout(2000)
    expect(page.get_by_test_id("issue-item")).to_be_visible()
    assert issue_exists("New Issue")

@pytest.mark.django_db(transaction=True)
def test_anonymous_user_cannot_create_issue(page: Page, live_server, test_project):
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    expect(page.get_by_test_id("issue-form")).not_to_be_visible()

# -------------------------------
# STATUS CHANGE - UŻYWAMY TEST-IDS
# -------------------------------
@pytest.mark.django_db(transaction=True)
def test_admin_can_change_issue_status(page: Page, live_server, test_project, test_issue, admin_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    
    status_select = page.get_by_test_id("status-select").first
    if status_select.count() > 0:
        expect(status_select).to_be_visible()
        status_select.select_option("in_progress")
        
        page.wait_for_timeout(2000)
        test_issue.refresh_from_db()
        assert test_issue.status == "in_progress"

@pytest.mark.django_db(transaction=True)
def test_reporter_cannot_change_status(page: Page, live_server, test_project, test_issue, reporter_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill("reporter")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    expect(page.get_by_test_id("status-select")).not_to_be_visible()

# -------------------------------
# COMMENTS - UŻYWAMY TEST-IDS
# -------------------------------
@pytest.mark.django_db(transaction=True)
def test_admin_can_add_comment(page: Page, live_server, test_project, test_issue, admin_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    
    # Kliknij na label zamiast checkbox (checkbox jest ukryty)
    comment_toggle_label = page.locator(f"label[for='toggle-comments-{test_issue.pk}']")
    comment_toggle_label.click()
    page.wait_for_timeout(1000)
    
    # Dodaj komentarz
    page.get_by_test_id("comment-content").fill("Admin comment")
    page.get_by_test_id("comment-submit").click()
    
    page.wait_for_timeout(2000)
    expect(page.get_by_test_id("comment-item")).to_be_visible()
    assert comment_exists(test_issue, "Admin comment", admin_user)

@pytest.mark.django_db(transaction=True)
def test_comment_count_updates_with_htmx(page: Page, live_server, test_project, test_issue, admin_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    
    # Sprawdź początkowy licznik
    comment_count = page.get_by_test_id(f"comment-count-{test_issue.pk}")
    expect(comment_count).to_contain_text("0")
    
    # Dodaj komentarz - kliknij label
    page.locator(f"label[for='toggle-comments-{test_issue.pk}']").click()
    page.get_by_test_id("comment-content").fill("Test comment")
    page.get_by_test_id("comment-submit").click()
    
    page.wait_for_timeout(2000)
    expect(comment_count).to_contain_text("1")

@pytest.mark.django_db(transaction=True)
def test_reporter_cannot_add_comments(page: Page, live_server, test_project, test_issue, reporter_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill("reporter")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    
    page.locator(f"label[for='toggle-comments-{test_issue.pk}']").click()
    expect(page.get_by_test_id("comment-form")).not_to_be_visible()

@pytest.mark.django_db(transaction=True)
def test_issue_list_updates_after_creation(page: Page, live_server, test_project, admin_user):
    page.goto(f"{live_server.url}/login/")
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("password123")
    page.get_by_test_id("login-submit").click()
    
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    
    initial_count = page.get_by_test_id("issue-item").count()

    page.get_by_test_id("issue-title").fill("HTMX Test Issue")
    page.get_by_test_id("issue-description").fill("Testing HTMX updates")
    page.get_by_test_id("issue-submit").click()
    
    page.wait_for_timeout(2000)
    
    # Sprawdź czy się dodało
    new_count = page.get_by_test_id("issue-item").count()
    assert new_count == initial_count + 1
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
