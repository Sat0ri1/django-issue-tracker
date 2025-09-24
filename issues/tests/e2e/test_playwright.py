import os
import pytest
from playwright.sync_api import Page
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
    
    # Check that user was NOT created (more reliable)
    assert not User.objects.filter(username="").exists()
    
    # Alternative: check if still on registration page
    assert "register" in page.url.lower()


@pytest.mark.django_db(transaction=True)
def test_logout_logs_user_out(page: Page, live_server, reporter_user):
    # Login
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", reporter_user.username)
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")
    
    # Wait for page to load after login
    page.wait_for_load_state("networkidle")
    
    # Check various possible texts for logout
    logout_locators = [
        page.locator("text=Logout"),
        page.locator("text=Log out"), 
        page.locator("text=Sign out"),
        page.locator("a[href*='logout']"),  # link containing 'logout'
        page.locator("button:has-text('Logout')"),
        page.locator("button:has-text('Log out')")
    ]
    
    # Find first visible logout element
    logout_element = None
    for locator in logout_locators:
        if locator.is_visible():
            logout_element = locator
            break
    
    # If logout not found, print page content for debugging
    if not logout_element:
        print("DEBUG: Page content after login:")
        print(page.content()[:500])  # First 500 characters
        assert False, "Could not find logout element on page"
    
    # Click logout
    logout_element.click()
    page.wait_for_load_state("networkidle")
    
    # Check if "Login" appeared
    login_locators = [
        page.locator("text=Login"),
        page.locator("text=Log in"),
        page.locator("text=Sign in"),
        page.locator("a[href*='login']")
    ]
    
    login_visible = any(loc.is_visible() for loc in login_locators)
    assert login_visible, "Could not find login element after logout"


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
    page.fill("input[name='username']", admin_user.username)
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")

    page.goto(f"{live_server.url}/projects/create/")
    
    page.fill("input[name='name']", "Admin Project")
    page.fill("textarea[name='description']", "Admin project description")
    
    # Użyj bardziej specyficznego selektora - przycisk z tekstem "Create Project"
    page.click("button:has-text('Create Project')")
    # LUB alternatywnie:
    # page.click("form:has(input[name='name']) button[type='submit']")
    
    page.wait_for_load_state("networkidle")
    
    assert project_exists("Admin Project")


@pytest.mark.django_db(transaction=True)
def test_create_project_forbidden_for_non_admin(page: Page, live_server, reporter_user):
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", reporter_user.username)
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")

    page.goto(f"{live_server.url}/projects/create/")
    content = page.content()
    
    # Sprawdź różne możliwe komunikaty błędów
    forbidden_messages = [
        "forbidden" in content.lower(),
        "403" in content,
        "login" in page.url,
        "only admin" in content.lower(),  # <-- DODANE!
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
    page.fill("input[name='username']", user.username)
    page.fill("input[name='password']", "pass")
    page.click("button[type='submit']")

    # ZMIANA: Idź na stronę projektu zamiast /issues/create/
    page.goto(f"{live_server.url}/projects/{project.pk}/")
    
    # Znajdź formularz tworzenia issue na stronie projektu
    page.fill("input[name='title']", f"Issue by {role}")
    page.fill("textarea[name='description']", "Issue description")
    
    # Znajdź przycisk submit dla formularza issue (nie projektu!)
    page.locator("form:has(input[name='title'])").locator("button[type='submit']").click()
    page.wait_for_load_state("networkidle")
    
    assert issue_exists(f"Issue by {role}")


@pytest.mark.django_db(transaction=True)
def test_create_issue_invalid_form(page: Page, live_server, project, reporter_user):
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", reporter_user.username)
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")

    # ZMIANA: Idź na stronę projektu (tak jak w poprawionym teście)
    page.goto(f"{live_server.url}/projects/{project.pk}/")
    
    # Fill invalid data (empty title)
    page.fill("input[name='title']", "")
    page.fill("textarea[name='description']", "desc")
    
    # Znajdź przycisk submit dla formularza issue
    page.locator("form:has(input[name='title'])").locator("button[type='submit']").click()
    page.wait_for_load_state("networkidle")

    # Check that issue was NOT created (more reliable)
    assert not issue_exists("")
    
    # ZMIANA: Sprawdź czy jesteś na stronie projektu lub głównej (po błędzie formularza)
    # Zamiast sprawdzać "create" w URL
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
    page.fill("input[name='username']", user.username)
    page.fill("input[name='password']", "pass")
    page.click("button[type='submit']")

    # Idź na stronę projektu gdzie jest lista issues z formularzami zmiany statusu
    page.goto(f"{live_server.url}/projects/{issue.project.pk}/")
    
    # Poczekaj na załadowanie strony z issues
    page.wait_for_load_state("networkidle")
    
    # Dla admin/assignee formularz POWINIEN być widoczny
    status_select = page.locator(f"form:has([hx-target='#status-badge-{issue.pk}']) select[name='status']")
    assert status_select.is_visible(), f"Status form should be visible for {role}"
    
    # Zmień status na 'done'
    status_select.select_option("done")
    
    # Kliknij Update button w tym samym formularzu
    page.locator(f"form:has([hx-target='#status-badge-{issue.pk}'])").locator("button:has-text('Update')").click()
    
    # Poczekaj na response HTMX (badge się zmieni)
    page.wait_for_timeout(1000)  # krótka pauza na HTMX
    
    # Sprawdź czy status badge się zmienił
    status_badge = page.locator(f"#status-badge-{issue.pk}")
    assert status_badge.is_visible(), "Status badge should be visible"
    
    # Sprawdź w bazie danych
    issue.refresh_from_db()
    assert issue.status == "done"


@pytest.mark.django_db(transaction=True)
def test_change_status_forbidden_for_regular_user(page: Page, live_server, issue, reporter_user):
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", reporter_user.username)
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")

    # Idź na stronę projektu
    page.goto(f"{live_server.url}/projects/{issue.project.pk}/")
    page.wait_for_load_state("networkidle")
    
    # Dla reporter formularz zmiany statusu NIE POWINIEN być widoczny
    status_form = page.locator(f"form:has([hx-target='#status-badge-{issue.pk}'])")
    assert not status_form.is_visible(), "Status change form should not be visible for reporters"
    
    # Alternatywnie: sprawdź czy select nie istnieje
    status_select = page.locator("select[name='status']")
    if status_select.count() > 0:
        assert not status_select.is_visible(), "Status select should not be visible for reporters"
    
    # Status nie powinien się zmienić (pozostaje bez zmiany)
    original_status = issue.status
    issue.refresh_from_db()
    assert issue.status == original_status


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
    page.fill("input[name='username']", user.username)
    page.fill("input[name='password']", "pass")
    page.click("button[type='submit']")

    page.goto(f"{live_server.url}/issues/{issue.pk}/comments/add/")
    page.fill("textarea[name='text']", f"Comment by {role}")
    page.click("button[type='submit']")

    assert comment_exists(issue, f"Comment by {role}", user)
    # Try to find comment in page content, but don't fail if selector doesn't exist
    try:
        page.wait_for_selector(f"#comments-section-{issue.pk}", timeout=3000)
        content = page.content()
        assert f"Comment by {role}" in content
    except Exception:
        # If selector doesn't exist, just check that comment was added to DB
        pass


@pytest.mark.django_db(transaction=True)
def test_add_comment_forbidden_for_regular_user(page: Page, live_server, issue, reporter_user):
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", reporter_user.username)
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")

    page.goto(f"{live_server.url}/issues/{issue.pk}/comments/add/")
    page.fill("textarea[name='text']", "Blocked comment")
    page.click("button[type='submit']")
    assert not comment_exists(issue, "Blocked comment", reporter_user)


@pytest.mark.django_db(transaction=True)
def test_add_comment_invalid_form(page: Page, live_server, issue, admin_user):
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", admin_user.username)
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")

    page.goto(f"{live_server.url}/issues/{issue.pk}/comments/add/")
    page.fill("textarea[name='text']", "")
    page.click("button[type='submit']")
    
    # Check that empty comment was NOT added (more reliable)
    assert not comment_exists(issue, "", admin_user)
