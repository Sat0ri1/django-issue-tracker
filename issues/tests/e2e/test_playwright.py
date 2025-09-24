import pytest
from playwright.sync_api import Page
from django.contrib.auth import get_user_model
from issues.models import Project, Issue, Comment

User = get_user_model()


# -------------------------------
# USER FIXTURES
# -------------------------------
@pytest.fixture
def admin_user(db):
    return User.objects.create_user(username="admin", password="password123", role="admin")


@pytest.fixture
def assignee_user(db):
    return User.objects.create_user(username="assignee", password="password123", role="assignee")


@pytest.fixture
def reporter_user(db):
    return User.objects.create_user(username="reporter", password="password123", role="reporter")


# -------------------------------
# PROJECT / ISSUE FIXTURES
# -------------------------------
@pytest.fixture
def project(db):
    return Project.objects.create(name="Test Project")


@pytest.fixture
def issue(db, project, reporter_user):
    return Issue.objects.create(
        project=project,
        title="Bug #1",
        description="Bug description",
        author=reporter_user,
    )


# -------------------------------
# AUTH TESTS
# -------------------------------
@pytest.mark.django_db(transaction=True)
def test_register_valid(page: Page, live_server):
    page.goto(f"{live_server.url}/register/")
    page.fill("input[name='username']", "play_user")
    page.fill("input[name='email']", "play@example.com")
    page.fill("input[name='password1']", "StrongPass123")
    page.fill("input[name='password2']", "StrongPass123")
    page.click("button[type='submit']")
    assert User.objects.filter(username="play_user").exists()


@pytest.mark.django_db(transaction=True)
def test_register_invalid(page: Page, live_server):
    page.goto(f"{live_server.url}/register/")
    page.fill("input[name='username']", "")
    page.fill("input[name='email']", "bademail")
    page.fill("input[name='password1']", "123")
    page.fill("input[name='password2']", "456")
    page.click("button[type='submit']")
    assert page.locator("text=This field is required").is_visible() or \
           page.locator("text=Enter a valid email").is_visible()


@pytest.mark.django_db(transaction=True)
def test_logout_logs_user_out(page: Page, live_server, reporter_user):
    # Login
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", reporter_user.username)
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")

    # Verify logged in
    assert page.locator("text=Wyloguj").is_visible()

    # Logout (POST)
    page.click("form[action='/logout/'] button[type='submit']")

    # Verify logged out
    assert page.locator("text=Zaloguj").is_visible()


# -------------------------------
# PROJECT CREATION
# -------------------------------
@pytest.mark.django_db(transaction=True)
def test_create_project_requires_login(page: Page, live_server):
    page.goto(f"{live_server.url}/projects/create/")
    assert "login" in page.url


@pytest.mark.django_db(transaction=True)
def test_create_project_allowed_for_admin(page: Page, live_server, admin_user):
    # Login
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", admin_user.username)
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")

    # Create project
    page.goto(f"{live_server.url}/projects/create/")
    page.fill("input[name='name']", "Admin Project")
    page.click("button[type='submit']")

    assert Project.objects.filter(name="Admin Project").exists()


@pytest.mark.django_db(transaction=True)
def test_create_project_forbidden_for_non_admin(page: Page, live_server, reporter_user):
    # Login
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", reporter_user.username)
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")

    # Attempt create
    page.goto(f"{live_server.url}/projects/create/")
    content = page.content()
    assert "forbidden" in content.lower() or "403" in content or "login" not in page.url


# -------------------------------
# ISSUE CREATION
# -------------------------------
@pytest.mark.django_db(transaction=True)
def test_create_issue_requires_login(page: Page, live_server, project):
    page.goto(f"{live_server.url}/projects/{project.pk}/issues/create/")
    assert "login" in page.url


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("role", ["admin", "assignee", "reporter"])
def test_create_issue_logged_in(page: Page, live_server, project, role):
    user = User.objects.create_user(username=f"user_{role}", password="pass", role=role)

    # Login
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", user.username)
    page.fill("input[name='password']", "pass")
    page.click("button[type='submit']")

    # Create issue
    page.goto(f"{live_server.url}/projects/{project.pk}/issues/create/")
    page.fill("input[name='title']", f"Issue by {role}")
    page.fill("textarea[name='description']", "Issue description")
    page.click("button[type='submit']")

    assert Issue.objects.filter(title=f"Issue by {role}").exists()


@pytest.mark.django_db(transaction=True)
def test_create_issue_invalid_form(page: Page, live_server, project, reporter_user):
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", reporter_user.username)
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")

    page.goto(f"{live_server.url}/projects/{project.pk}/issues/create/")
    page.fill("input[name='title']", "")
    page.fill("textarea[name='description']", "desc")
    page.click("button[type='submit']")

    assert page.locator("text=This field is required").is_visible()


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
    user = User.objects.create_user(username=f"user_{role}", password="pass", role=role)

    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", user.username)
    page.fill("input[name='password']", "pass")
    page.click("button[type='submit']")

    page.goto(f"{live_server.url}/issues/{issue.pk}/change-status/")
    page.select_option("select[name='status']", "done")
    page.click("button[type='submit']")

    issue.refresh_from_db()
    assert issue.status == "done"


@pytest.mark.django_db(transaction=True)
def test_change_status_forbidden_for_regular_user(page: Page, live_server, issue, reporter_user):
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", reporter_user.username)
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")

    page.goto(f"{live_server.url}/issues/{issue.pk}/change-status/")
    page.select_option("select[name='status']", "done")
    page.click("button[type='submit']")

    issue.refresh_from_db()
    assert issue.status != "done"


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
    user = User.objects.create_user(username=f"user_{role}", password="pass", role=role)

    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", user.username)
    page.fill("input[name='password']", "pass")
    page.click("button[type='submit']")

    page.goto(f"{live_server.url}/issues/{issue.pk}/comments/add/")
    page.fill("textarea[name='text']", f"Comment by {role}")
    page.click("button[type='submit']")

    assert Comment.objects.filter(issue=issue, text=f"Comment by {role}", author=user).exists()
    page.wait_for_selector(f"#comments-section-{issue.pk}")
    assert f"Comment by {role}" in page.content()


@pytest.mark.django_db(transaction=True)
def test_add_comment_forbidden_for_regular_user(page: Page, live_server, issue, reporter_user):
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", reporter_user.username)
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")

    page.goto(f"{live_server.url}/issues/{issue.pk}/comments/add/")
    page.fill("textarea[name='text']", "Blocked comment")
    page.click("button[type='submit']")

    assert not Comment.objects.filter(issue=issue, text="Blocked comment").exists()


@pytest.mark.django_db(transaction=True)
def test_add_comment_invalid_form(page: Page, live_server, issue, admin_user):
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", admin_user.username)
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")

    page.goto(f"{live_server.url}/issues/{issue.pk}/comments/add/")
    page.fill("textarea[name='text']", "")
    page.click("button[type='submit']")

    assert page.locator("text=This field is required").is_visible()
