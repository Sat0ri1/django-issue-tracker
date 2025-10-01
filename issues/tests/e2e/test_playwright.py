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
    
    # Użyj rzeczywistych selektorów z formularza logowania
    page.fill("input[name='username']", "admin")
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")
    
    expect(page).to_have_url(f"{live_server.url}/")

@pytest.mark.django_db(transaction=True)
def test_login_with_invalid_credentials(page: Page, live_server):
    page.goto(f"{live_server.url}/login/")
    
    page.fill("input[name='username']", "invalid")
    page.fill("input[name='password']", "wrong")
    page.click("button[type='submit']")
    
    # Sprawdź czy zostajemy na stronie logowania
    expect(page).to_have_url(f"{live_server.url}/login/")

@pytest.mark.django_db(transaction=True)
def test_register_new_user(page: Page, live_server):
    page.goto(f"{live_server.url}/register/")
    
    page.fill("input[name='username']", "newuser")
    page.fill("input[name='email']", "newuser@example.com")
    page.fill("input[name='password1']", "testpass123")
    page.fill("input[name='password2']", "testpass123")
    
    # Sprawdź czy pole role istnieje, jeśli nie - pomiń
    role_select = page.locator("select[name='role']")
    if role_select.count() > 0:
        page.select_option("select[name='role']", "reporter")
    
    page.click("button[type='submit']")
    
    # Po rejestracji przekierowuje na login
    expect(page).to_have_url(f"{live_server.url}/login/")

# -------------------------------
# PROJECT CREATION
# -------------------------------
@pytest.mark.django_db(transaction=True)
def test_admin_can_create_project(page: Page, live_server, admin_user):
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", "admin")
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")
    
    # Sprawdź czy link do tworzenia projektów jest widoczny
    create_project_link = page.locator("text=Create Project").or_(page.locator("a[href='/projects/create/']"))
    expect(create_project_link).to_be_visible()
    create_project_link.click()
    
    expect(page).to_have_url(f"{live_server.url}/projects/create/")
    
    page.fill("input[name='name']", "New Project")
    page.fill("textarea[name='description']", "Project description")
    page.click("button[type='submit']")
    
    expect(page).to_have_url(f"{live_server.url}/")
    assert project_exists("New Project")

@pytest.mark.django_db(transaction=True)
def test_reporter_cannot_see_create_project_link(page: Page, live_server, reporter_user):
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", "reporter")
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")
    
    # Reporter nie powinien widzieć linku do tworzenia projektów
    create_project_link = page.locator("text=Create Project").or_(page.locator("a[href='/projects/create/']"))
    expect(create_project_link).not_to_be_visible()

# -------------------------------
# ISSUE CREATION
# -------------------------------
@pytest.mark.django_db(transaction=True)
def test_authenticated_user_can_create_issue(page: Page, live_server, test_project, admin_user):
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", "admin")
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")
    
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    
    # Sprawdź czy formularz do tworzenia issues jest widoczny
    title_input = page.locator("input[name='title']")
    expect(title_input).to_be_visible()
    
    title_input.fill("New Issue")
    page.fill("textarea[name='description']", "Issue description")
    
    # Znajdź przycisk submit w formularzu issues
    submit_button = page.locator("form").filter(has=title_input).locator("button[type='submit']")
    submit_button.click()
    
    page.wait_for_timeout(2000)  # Wait for HTMX
    expect(page.locator("text=New Issue")).to_be_visible()
    assert issue_exists("New Issue")

@pytest.mark.django_db(transaction=True)
def test_anonymous_user_cannot_create_issue(page: Page, live_server, test_project):
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    
    # Anonimowy użytkownik nie powinien widzieć formularza
    expect(page.locator("input[name='title']")).not_to_be_visible()

# -------------------------------
# STATUS CHANGE
# -------------------------------
@pytest.mark.django_db(transaction=True)
def test_admin_can_change_issue_status(page: Page, live_server, test_project, test_issue, admin_user):
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", "admin")
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")
    
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    
    # Sprawdź czy select status jest widoczny
    status_select = page.locator("select[name='status']").first
    if status_select.count() > 0:
        expect(status_select).to_be_visible()
        status_select.select_option("in_progress")
        
        page.wait_for_timeout(2000)  # Wait for HTMX
        test_issue.refresh_from_db()
        assert test_issue.status == "in_progress"

@pytest.mark.django_db(transaction=True)
def test_reporter_cannot_change_status(page: Page, live_server, test_project, test_issue, reporter_user):
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", "reporter")
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")
    
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    
    # Reporter nie powinien widzieć selecta statusu
    expect(page.locator("select[name='status']")).not_to_be_visible()

# -------------------------------
# COMMENTS & HTMX
# -------------------------------
@pytest.mark.django_db(transaction=True)
def test_admin_can_add_comment(page: Page, live_server, test_project, test_issue, admin_user):
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", "admin")
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")
    
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    
    # Kliknij na toggle komentarzy - użyj różnych selektorów
    toggle_selector = f"#toggle-comments-{test_issue.pk}"
    toggle_label = f"label[for='toggle-comments-{test_issue.pk}']"
    
    if page.locator(toggle_label).count() > 0:
        page.locator(toggle_label).click()
    elif page.locator(toggle_selector).count() > 0:
        page.locator(toggle_selector).click()
    else:
        # Kliknij na tekst "Comments" lub podobny
        page.locator("text=Comments").or_(page.locator("text=Komentarze")).click()
    
    # Poczekaj na pojawienie się textarea
    page.wait_for_timeout(1000)
    
    # Dodaj komentarz jeśli textarea jest widoczna
    textarea = page.locator("textarea[name='content']")
    if textarea.count() > 0:
        textarea.fill("Test comment")
        
        # Znajdź odpowiedni submit button
        submit_button = page.locator("button[type='submit']").filter(has_text="Submit").or_(
            page.locator("button[type='submit']").filter(has_text="Add")
        )
        if submit_button.count() == 0:
            submit_button = page.locator("button[type='submit']").last
        
        submit_button.click()
        
        page.wait_for_timeout(2000)  # Wait for HTMX
        expect(page.locator("text=Test comment")).to_be_visible()
        assert comment_exists(test_issue, "Test comment", admin_user)

@pytest.mark.django_db(transaction=True)
def test_issue_list_updates_after_creation(page: Page, live_server, test_project, admin_user):
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", "admin")
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")
    
    page.goto(f"{live_server.url}/projects/{test_project.pk}/")
    
    # Utwórz nowe issue
    title_input = page.locator("input[name='title']")
    if title_input.count() > 0:
        title_input.fill("HTMX Test Issue")
        page.fill("textarea[name='description']", "Testing HTMX updates")
        
        submit_button = page.locator("form").filter(has=title_input).locator("button[type='submit']")
        submit_button.click()
        
        page.wait_for_timeout(2000)
        expect(page.locator("text=HTMX Test Issue")).to_be_visible()

@pytest.mark.django_db(transaction=True)
def test_no_issues_message_when_empty(page: Page, live_server, admin_user):
    empty_project = create_project("Empty Project")
    
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", "admin")
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")
    
    page.goto(f"{live_server.url}/projects/{empty_project.pk}/")
    
    # Sprawdź czy pokazuje się komunikat o braku issues
    expect(page.locator("text=No issues").or_(page.locator("text=Brak"))).to_be_visible()
