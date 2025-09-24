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
    
    # Use a more specific selector - button with text "Create Project"
    page.click("button:has-text('Create Project')")
    # OR alternatively:
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
    
    # Check various possible forbidden messages
    forbidden_messages = [
        "forbidden" in content.lower(),
        "403" in content,
        "login" in page.url,
        "only admin" in content.lower(),  # <-- ADDED!
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

    # CHANGE: Go to project page instead of /issues/create/
    page.goto(f"{live_server.url}/projects/{project.pk}/")
    
    # Find issue creation form on the project page
    page.fill("input[name='title']", f"Issue by {role}")
    page.fill("textarea[name='description']", "Issue description")
    
    # Find submit button for issue form (not project!)
    page.locator("form:has(input[name='title'])").locator("button[type='submit']").click()
    page.wait_for_load_state("networkidle")
    
    assert issue_exists(f"Issue by {role}")


@pytest.mark.django_db(transaction=True)
def test_create_issue_invalid_form(page: Page, live_server, project, reporter_user):
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", reporter_user.username)
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")

    # CHANGE: Go to project page (as in the updated test)
    page.goto(f"{live_server.url}/projects/{project.pk}/")
    
    # Fill invalid data (empty title)
    page.fill("input[name='title']", "")
    page.fill("textarea[name='description']", "desc")
    
    # Find submit button for issue form
    page.locator("form:has(input[name='title'])").locator("button[type='submit']").click()
    page.wait_for_load_state("networkidle")

    # Check that issue was NOT created (more reliable)
    assert not issue_exists("")
    
    # CHANGE: Check if you are on the project or main page (after form error)
    # Instead of checking "create" in URL
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

    # Go to project page where issues with status change forms are listed
    page.goto(f"{live_server.url}/projects/{issue.project.pk}/")
    
    # Wait for issues to load
    page.wait_for_load_state("networkidle")
    
    # DEBUG: Check what is on the page
    print(f"DEBUG: Issue ID: {issue.pk}")
    print(f"DEBUG: User role: {role}")
    
    # Check various selectors
    all_forms = page.locator("form").count()
    status_selects = page.locator("select[name='status']").count()
    update_buttons = page.locator("button:has-text('Update')").count()
    
    print(f"DEBUG: Forms on page: {all_forms}")
    print(f"DEBUG: Status selects: {status_selects}")
    print(f"DEBUG: Update buttons: {update_buttons}")
    
    # Check HTML for debugging
    if status_selects == 0:
        print("DEBUG: Page content (first 1000 chars):")
        print(page.content()[:1000])
    
    # Simpler selector - just select[name='status']
    status_select = page.locator("select[name='status']")
    assert status_select.count() > 0, f"No status select found for {role}"
    assert status_select.is_visible(), f"Status select should be visible for {role}"
    
    # Change status to 'done'
    status_select.select_option("done")
    
    # Click the first available Update button
    update_button = page.locator("button:has-text('Update')")
    assert update_button.count() > 0, "No Update button found"
    update_button.first.click()
    
    # Wait for HTMX response
    page.wait_for_timeout(1000)
    
    # Check in the database
    issue.refresh_from_db()
    assert issue.status == "done"


@pytest.mark.django_db(transaction=True)
def test_change_status_forbidden_for_regular_user(page: Page, live_server, issue, reporter_user):
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", reporter_user.username)
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")

    # Go to project page
    page.goto(f"{live_server.url}/projects/{issue.project.pk}/")
    page.wait_for_load_state("networkidle")
    
    # For reporter, status change form should NOT be visible
    status_form = page.locator(f"form:has([hx-target='#status-badge-{issue.pk}'])")
    assert not status_form.is_visible(), "Status change form should not be visible for reporters"
    
    # Alternatively: check if select does not exist
    status_select = page.locator("select[name='status']")
    if status_select.count() > 0:
        assert not status_select.is_visible(), "Status select should not be visible for reporters"
    
    # Status should not change (remains unchanged)
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

    # CHANGE: Go to project page where issues with comments are listed
    page.goto(f"{live_server.url}/projects/{issue.project.pk}/")
    page.wait_for_load_state("networkidle")
    
    # CHANGE: Open comments section (click on details summary)
    comments_summary = page.locator("summary:has-text('Comments')")
    if comments_summary.is_visible():
        comments_summary.click()
        page.wait_for_timeout(500)  # Wait for details to open
    
    # Now fill the comment form
    textarea = page.locator("textarea[name='text']")
    
    # Debug if textarea is not visible
    if not textarea.is_visible():
        print("DEBUG: Textarea not visible, page content:")
        print(page.content()[:1000])
        
        # Try to find other selectors
        all_textareas = page.locator("textarea").count()
        print(f"DEBUG: All textareas on page: {all_textareas}")
        
        # Check if comments section exists
        comments_sections = page.locator("[id*='comments']").count()
        print(f"DEBUG: Comments sections: {comments_sections}")
    
    assert textarea.is_visible(), f"Comment textarea should be visible for {role}"
    
    textarea.fill(f"Comment by {role}")
    
    # Find Add Comment button
    add_button = page.locator("button:has-text('Add Comment')")
    assert add_button.is_visible(), "Add Comment button should be visible"
    add_button.click()
    
    page.wait_for_timeout(1000)  # Wait for HTMX response
    
    # Check in the database
    assert comment_exists(issue, f"Comment by {role}", user)


@pytest.mark.django_db(transaction=True)
def test_add_comment_forbidden_for_regular_user(page: Page, live_server, issue, reporter_user):
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", reporter_user.username)
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")

    # CHANGE: Go to project page
    page.goto(f"{live_server.url}/projects/{issue.project.pk}/")
    page.wait_for_load_state("networkidle")
    
    # CHANGE: Try to open comments
    comments_summary = page.locator("summary:has-text('Comments')")
    if comments_summary.is_visible():
        comments_summary.click()
        page.wait_for_timeout(500)
    
    # For reporter, comment form should NOT be visible
    textarea = page.locator("textarea[name='text']")
    assert not textarea.is_visible(), "Comment form should not be visible for reporters"
    
    # Status should not change
    assert not comment_exists(issue, "Blocked comment", reporter_user)


@pytest.mark.django_db(transaction=True)
def test_add_comment_invalid_form(page: Page, live_server, issue, admin_user):
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name='username']", admin_user.username)
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")

    # CHANGE: Go to project page
    page.goto(f"{live_server.url}/projects/{issue.project.pk}/")
    page.wait_for_load_state("networkidle")
    
    # Open comments
    comments_summary = page.locator("summary:has-text('Comments')")
    if comments_summary.is_visible():
        comments_summary.click()
        page.wait_for_timeout(500)
    
    # Fill with empty text
    textarea = page.locator("textarea[name='text']")
    textarea.fill("")
    
    add_button = page.locator("button:has-text('Add Comment')")
    add_button.click()
    
    page.wait_for_timeout(1000)
    
    # Empty comment should not be added
    assert not comment_exists(issue, "", admin_user)
