import pytest
from playwright.async_api import Page
from django.contrib.auth import get_user_model
from issues.models import Project, Issue, Comment
from asgiref.sync import sync_to_async

User = get_user_model()

# -------------------------------
# HELPERS (SYNC -> ASYNC)
# -------------------------------
@sync_to_async
def create_user(username, password, role="reporter"):
    return User.objects.create_user(username=username, password=password, role=role)

@sync_to_async
def create_project(name="Test Project"):
    return Project.objects.create(name=name)

@sync_to_async
def create_issue(project, author, title="Bug #1", description="Bug description"):
    return Issue.objects.create(project=project, author=author, title=title, description=description)

@sync_to_async
def project_exists(name):
    return Project.objects.filter(name=name).exists()

@sync_to_async
def issue_exists(title):
    return Issue.objects.filter(title=title).exists()

@sync_to_async
def comment_exists(issue, text, author):
    return Comment.objects.filter(issue=issue, text=text, author=author).exists()

@sync_to_async
def refresh(obj):
    obj.refresh_from_db()

# -------------------------------
# FIXTURES
# -------------------------------
@pytest.fixture
async def admin_user(db):
    return await create_user("admin", "password123", role="admin")

@pytest.fixture
async def assignee_user(db):
    return await create_user("assignee", "password123", role="assignee")

@pytest.fixture
async def reporter_user(db):
    return await create_user("reporter", "password123", role="reporter")

@pytest.fixture
async def project(db):
    return await create_project()

@pytest.fixture
async def issue(db, project, reporter_user):
    return await create_issue(project, reporter_user)

# -------------------------------
# AUTH TESTS
# -------------------------------
@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_register_valid(page: Page, live_server):
    await page.goto(f"{live_server.url}/register/")
    await page.fill("input[name='username']", "play_user")
    await page.fill("input[name='email']", "play@example.com")
    await page.fill("input[name='password1']", "StrongPass123")
    await page.fill("input[name='password2']", "StrongPass123")
    await page.click("button[type='submit']")
    assert await User.objects.filter(username="play_user").aexists()

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_register_invalid(page: Page, live_server):
    await page.goto(f"{live_server.url}/register/")
    await page.fill("input[name='username']", "")
    await page.fill("input[name='email']", "bademail")
    await page.fill("input[name='password1']", "123")
    await page.fill("input[name='password2']", "456")
    await page.click("button[type='submit']")
    content = await page.content()
    assert "This field is required" in content or "Enter a valid email" in content

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_logout_logs_user_out(page: Page, live_server, reporter_user):
    await page.goto(f"{live_server.url}/login/")
    await page.fill("input[name='username']", reporter_user.username)
    await page.fill("input[name='password']", "password123")
    await page.click("button[type='submit']")
    assert await page.locator("text=Logout").is_visible()
    await page.click("text=Logout")
    assert await page.locator("text=Login").is_visible()

# -------------------------------
# PROJECT CREATION
# -------------------------------
@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_create_project_requires_login(page: Page, live_server):
    await page.goto(f"{live_server.url}/projects/create/")
    assert "login" in page.url

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_create_project_allowed_for_admin(page: Page, live_server, admin_user):
    await page.goto(f"{live_server.url}/login/")
    await page.fill("input[name='username']", admin_user.username)
    await page.fill("input[name='password']", "password123")
    await page.click("button[type='submit']")

    await page.goto(f"{live_server.url}/projects/create/")
    await page.fill("input[name='name']", "Admin Project")
    await page.click("button[type='submit']")
    assert await project_exists("Admin Project")

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_create_project_forbidden_for_non_admin(page: Page, live_server, reporter_user):
    await page.goto(f"{live_server.url}/login/")
    await page.fill("input[name='username']", reporter_user.username)
    await page.fill("input[name='password']", "password123")
    await page.click("button[type='submit']")

    await page.goto(f"{live_server.url}/projects/create/")
    content = await page.content()
    assert "forbidden" in content.lower() or "403" in content or "login" not in page.url

# -------------------------------
# ISSUE CREATION
# -------------------------------
@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_create_issue_requires_login(page: Page, live_server, project):
    await page.goto(f"{live_server.url}/projects/{project.pk}/issues/create/")
    assert "login" in page.url

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["admin", "assignee", "reporter"])
async def test_create_issue_logged_in(page: Page, live_server, project, db, role):
    user = await create_user(f"user_{role}", "pass", role=role)
    await page.goto(f"{live_server.url}/login/")
    await page.fill("input[name='username']", user.username)
    await page.fill("input[name='password']", "pass")
    await page.click("button[type='submit']")

    await page.goto(f"{live_server.url}/projects/{project.pk}/issues/create/")
    await page.fill("input[name='title']", f"Issue by {role}")
    await page.fill("textarea[name='description']", "Issue description")
    await page.click("button[type='submit']")
    assert await issue_exists(f"Issue by {role}")

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_create_issue_invalid_form(page: Page, live_server, project, reporter_user):
    await page.goto(f"{live_server.url}/login/")
    await page.fill("input[name='username']", reporter_user.username)
    await page.fill("input[name='password']", "password123")
    await page.click("button[type='submit']")

    await page.goto(f"{live_server.url}/projects/{project.pk}/issues/create/")
    await page.fill("input[name='title']", "")
    await page.fill("textarea[name='description']", "desc")
    await page.click("button[type='submit']")

    content = await page.content()
    assert "This field is required" in content or "title" in content.lower()

# -------------------------------
# STATUS CHANGE
# -------------------------------
@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_change_status_requires_login(page: Page, live_server, issue):
    await page.goto(f"{live_server.url}/issues/{issue.pk}/change-status/")
    assert "login" in page.url

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["admin", "assignee"])
async def test_change_status_allowed(page: Page, live_server, issue, role):
    user = await create_user(f"user_{role}", "pass", role=role)
    await page.goto(f"{live_server.url}/login/")
    await page.fill("input[name='username']", user.username)
    await page.fill("input[name='password']", "pass")
    await page.click("button[type='submit']")

    await page.goto(f"{live_server.url}/issues/{issue.pk}/change-status/")
    await page.select_option("select[name='status']", "done")
    await page.click("button[type='submit']")
    await refresh(issue)
    assert issue.status == "done"

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_change_status_forbidden_for_regular_user(page: Page, live_server, issue, reporter_user):
    await page.goto(f"{live_server.url}/login/")
    await page.fill("input[name='username']", reporter_user.username)
    await page.fill("input[name='password']", "password123")
    await page.click("button[type='submit']")

    await page.goto(f"{live_server.url}/issues/{issue.pk}/change-status/")
    await page.select_option("select[name='status']", "done")
    await page.click("button[type='submit']")
    await refresh(issue)
    assert issue.status != "done"

# -------------------------------
# COMMENTS & HTMX
# -------------------------------
@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_add_comment_requires_login(page: Page, live_server, issue):
    await page.goto(f"{live_server.url}/issues/{issue.pk}/comments/add/")
    assert "login" in page.url

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["admin", "assignee"])
async def test_add_comment_allowed(page: Page, live_server, issue, role):
    user = await create_user(f"user_{role}", "pass", role=role)
    await page.goto(f"{live_server.url}/login/")
    await page.fill("input[name='username']", user.username)
    await page.fill("input[name='password']", "pass")
    await page.click("button[type='submit']")

    await page.goto(f"{live_server.url}/issues/{issue.pk}/comments/add/")
    await page.fill("textarea[name='text']", f"Comment by {role}")
    await page.click("button[type='submit']")

    assert await comment_exists(issue, f"Comment by {role}", user)
    await page.wait_for_selector(f"#comments-section-{issue.pk}")
    content = await page.content()
    assert f"Comment by {role}" in content

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_add_comment_forbidden_for_regular_user(page: Page, live_server, issue, reporter_user):
    await page.goto(f"{live_server.url}/login/")
    await page.fill("input[name='username']", reporter_user.username)
    await page.fill("input[name='password']", "password123")
    await page.click("button[type='submit']")

    await page.goto(f"{live_server.url}/issues/{issue.pk}/comments/add/")
    await page.fill("textarea[name='text']", "Blocked comment")
    await page.click("button[type='submit']")
    assert not await comment_exists(issue, "Blocked comment", reporter_user)

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_add_comment_invalid_form(page: Page, live_server, issue, admin_user):
    await page.goto(f"{live_server.url}/login/")
    await page.fill("input[name='username']", admin_user.username)
    await page.fill("input[name='password']", "password123")
    await page.click("button[type='submit']")

    await page.goto(f"{live_server.url}/issues/{issue.pk}/comments/add/")
    await page.fill("textarea[name='text']", "")
    await page.click("button[type='submit']")
    content = await page.content()
    assert "This field is required" in content
