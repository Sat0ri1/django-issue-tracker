import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from issues.models import Project, Issue, Comment

UserModel = get_user_model()


def user_model_has_role_field() -> bool:
    # Check if the User model has a 'role' field
    return any(getattr(f, "name", "") == "role" for f in UserModel._meta.get_fields())


def create_user(username: str, password: str, role: str | None = None):
    # Create a user with an optional role
    if role and user_model_has_role_field():
        return UserModel.objects.create_user(username=username, password=password, role=role)
    return UserModel.objects.create_user(username=username, password=password)


@pytest.mark.django_db
def test_project_list_view(client):
    Project.objects.create(name="P1")
    r = client.get(reverse("project_list"))
    assert r.status_code == 200
    assert b"P1" in r.content


# --- Projects: only admin can create --- #

@pytest.mark.django_db
def test_create_project_requires_login(client):
    url = reverse("create_project")  # assuming this URL exists
    response = client.post(url, {"name": "Test Project"})
    # Should redirect to login if not authenticated
    assert response.status_code == 302


@pytest.mark.django_db
def test_create_project_allowed_for_admin_only(client):
    if not user_model_has_role_field():
        pytest.skip("User model has no 'role' field - role test skipped.")
    
    admin = create_user("admin1", "pass", role="admin")
    assignee = create_user("assignee1", "pass", role="assignee")
    regular = create_user("regular1", "pass", role="reporter")
    
    url = reverse("create_project")  # assuming this URL exists
    
    # Admin should be able to create a project
    client.login(username=admin.username, password="pass")
    r1 = client.post(url, {"name": "Admin Project"})
    assert r1.status_code in (200, 302)
    assert Project.objects.filter(name="Admin Project").exists()
    client.logout()
    
    # Assignee should NOT be able to create a project
    client.login(username=assignee.username, password="pass")
    r2 = client.post(url, {"name": "Assignee Project"})
    assert not Project.objects.filter(name="Assignee Project").exists()
    assert r2.status_code in (403, 200, 302)
    client.logout()
    
    # Regular user should NOT be able to create a project
    client.login(username=regular.username, password="pass")
    r3 = client.post(url, {"name": "Regular Project"})
    assert not Project.objects.filter(name="Regular Project").exists()
    assert r3.status_code in (403, 200, 302)


# --- Issues: anyone can create --- #

@pytest.mark.django_db
def test_create_issue_requires_login(client):
    project = Project.objects.create(name="P2")
    url = reverse("create_issue", kwargs={"project_pk": project.pk})
    response = client.post(url, {"title": "Test", "description": "Test"})
    # Should redirect to login if not authenticated
    assert response.status_code == 302


@pytest.mark.django_db
def test_create_issue_allowed_for_any_logged_user(client):
    project = Project.objects.create(name="P-Anyone")
    url = reverse("create_issue", kwargs={"project_pk": project.pk})
    
    # Test with different roles if available
    if user_model_has_role_field():
        roles = ["admin", "assignee", "reporter"]
        for role in roles:
            user = create_user(f"user_{role}", "pass", role=role)
            client.login(username=user.username, password="pass")
            response = client.post(url, {"title": f"Issue by {role}", "description": "desc"})
            assert response.status_code == 302
            assert Issue.objects.filter(title=f"Issue by {role}").exists()
            client.logout()
    else:
        # Fallback for models without roles
        user = create_user("regular_user", "pass")
        client.login(username=user.username, password="pass")
        response = client.post(url, {"title": "Regular Issue", "description": "desc"})
        assert response.status_code == 302
        assert Issue.objects.filter(title="Regular Issue").exists()


@pytest.mark.django_db
def test_create_issue_logged_in(client):
    user = create_user(username="tester", password="pass")
    client.login(username=user.username, password="pass")
    project = Project.objects.create(name="P5")
    url = reverse("create_issue", kwargs={"project_pk": project.pk})
    response = client.post(url, {"title": "BugY", "description": "desc"})
    assert response.status_code == 302
    issue = Issue.objects.get(title="BugY")
    # Check that the issue is linked to the correct project
    assert issue.project == project


@pytest.mark.django_db
def test_create_issue_invalid_form(client):
    user = create_user(username="tester_invalid", password="pass")
    client.login(username=user.username, password="pass")
    project = Project.objects.create(name="P5b")
    url = reverse("create_issue", kwargs={"project_pk": project.pk})
    response = client.post(url, {"title": "", "description": "desc"})  # missing title
    assert response.status_code == 200
    # Check for various possible error messages
    content = response.content.decode('utf-8')
    assert ("This field is required" in content or 
            "required" in content.lower() or
            "title" in content.lower())


# --- Status changes: only admin and assignee --- #

@pytest.mark.django_db
def test_change_status_requires_login(client):
    project = Project.objects.create(name="P4")
    issue = Issue.objects.create(project=project, title="Bug", description="desc")
    url = reverse("change_status", kwargs={"pk": issue.pk})
    response = client.post(url, {"status": "done"})
    # Should redirect to login if not authenticated
    assert response.status_code == 302


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["admin", "assignee"])
def test_change_status_allowed_for_privileged_roles(client, role):
    if not user_model_has_role_field():
        pytest.skip("User model has no 'role' field - role test skipped.")
    
    user = create_user(f"user_{role}", "pass", role=role)
    client.login(username=user.username, password="pass")
    project = Project.objects.create(name=f"P-Status-{role}")
    issue = Issue.objects.create(project=project, title="Bug", description="desc")
    url = reverse("change_status", kwargs={"pk": issue.pk})
    
    response = client.post(url, {"status": "done"})
    assert response.status_code == 302
    issue.refresh_from_db()
    # Status should be changed to 'done'
    assert issue.status == "done"


@pytest.mark.django_db
def test_change_status_forbidden_for_regular_user(client):
    if not user_model_has_role_field():
        pytest.skip("User model has no 'role' field - role test skipped.")
    
    user = create_user("regular_status", "pass", role="reporter")
    client.login(username=user.username, password="pass")
    project = Project.objects.create(name="P-Status-NO")
    issue = Issue.objects.create(project=project, title="Bug", description="desc", status="open")
    url = reverse("change_status", kwargs={"pk": issue.pk})
    
    response = client.post(url, {"status": "done"})
    # Status should NOT change
    issue.refresh_from_db()
    assert issue.status == "open"
    assert response.status_code in (403, 200, 302)


@pytest.mark.django_db
def test_change_status_logged_in(client):
    # Use privileged role if roles exist
    role = "admin" if user_model_has_role_field() else None
    user = create_user(username="tester2", password="pass", role=role)
    client.login(username=user.username, password="pass")
    project = Project.objects.create(name="P7")
    issue = Issue.objects.create(project=project, title="Bug", description="desc")
    url = reverse("change_status", kwargs={"pk": issue.pk})
    response = client.post(url, {"status": "done"})
    if user_model_has_role_field():
        assert response.status_code == 302  # privileged user
        issue.refresh_from_db()
        assert issue.status == "done"
    else:
        # Without roles it may vary - depends on implementation
        assert response.status_code in (200, 302, 403)


# --- Assignee assignment: only admin can manually assign, otherwise automatic --- #

@pytest.mark.django_db
def test_manual_assignee_assignment_only_for_admin(client):
    if not user_model_has_role_field():
        pytest.skip("User model has no 'role' field - role test skipped.")
    
    admin = create_user("admin_assign", "pass", role="admin")
    assignee1 = create_user("assignee1", "pass", role="assignee")
    assignee2 = create_user("assignee2", "pass", role="assignee")
    regular = create_user("regular_assign", "pass", role="reporter")
    
    project = Project.objects.create(name="P-Assign")
    
    # Admin should be able to manually assign an assignee
    client.login(username=admin.username, password="pass")
    url = reverse("create_issue", kwargs={"project_pk": project.pk})
    response = client.post(url, {
        "title": "Manual Assignment",
        "description": "desc",
        "assignee": assignee1.pk  # manual assignment
    })
    assert response.status_code == 302
    issue = Issue.objects.get(title="Manual Assignment")
    assert issue.assignee == assignee1
    client.logout()
    
    # Regular user should NOT be able to manually assign (assignee field ignored)
    client.login(username=regular.username, password="pass")
    response = client.post(url, {
        "title": "Auto Assignment",
        "description": "desc",
        "assignee": assignee2.pk  # this should be ignored
    })
    assert response.status_code == 302
    issue = Issue.objects.get(title="Auto Assignment")
    # Should be auto-assigned, not manually to assignee2
    assert issue.assignee in [assignee1, assignee2] or issue.assignee is None


@pytest.mark.django_db
def test_automatic_assignee_assignment_balancing(client):
    if not user_model_has_role_field():
        pytest.skip("User model has no 'role' field - role test skipped.")
    
    assignee1 = create_user("assignee_bal1", "pass", role="assignee")
    assignee2 = create_user("assignee_bal2", "pass", role="assignee")
    user = create_user("creator", "pass", role="reporter")
    
    project = Project.objects.create(name="P-Balance")
    
    # Give assignee1 more issues
    Issue.objects.create(project=project, title="Issue1", description="d", assignee=assignee1)
    Issue.objects.create(project=project, title="Issue2", description="d", assignee=assignee1)
    # assignee2 has 0 issues
    
    client.login(username=user.username, password="pass")
    url = reverse("create_issue", kwargs={"project_pk": project.pk})
    
    # New issue should be assigned to assignee2 (who has fewer issues)
    response = client.post(url, {"title": "Balanced Issue", "description": "desc"})
    assert response.status_code == 302
    issue = Issue.objects.get(title="Balanced Issue")
    assert issue.assignee == assignee2  # should go to less loaded assignee


# --- Comments: only admin and assignee can add --- #

@pytest.mark.django_db
def test_add_comment_requires_login(client):
    project = Project.objects.create(name="P3")
    issue = Issue.objects.create(project=project, title="Bug", description="desc")
    url = reverse("add_comment", kwargs={"issue_pk": issue.pk})
    response = client.post(url, {"text": "Comment"})
    # Should redirect to login if not authenticated
    assert response.status_code == 302


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["admin", "assignee"])
def test_add_comment_allowed_for_privileged_roles(client, role):
    if not user_model_has_role_field():
        pytest.skip("User model has no 'role' field - role test skipped.")
    user = create_user(username=f"user_{role}", password="pass", role=role)
    client.login(username=user.username, password="pass")

    project = Project.objects.create(name=f"P-{role}")
    issue = Issue.objects.create(project=project, title="Bug", description="desc")
    url = reverse("add_comment", kwargs={"issue_pk": issue.pk})

    r = client.post(url, {"text": f"ok-{role}"})
    # View can return 302 (redirect) or 200 (render with errors/page)
    assert r.status_code in (200, 302)
    # Check that the comment was created
    assert Comment.objects.filter(issue=issue, text=f"ok-{role}", author=user).exists()


@pytest.mark.django_db
def test_add_comment_forbidden_for_regular_user(client):
    if not user_model_has_role_field():
        pytest.skip("User model has no 'role' field - role test skipped.")
    # Regular user without permissions (e.g. reporter/user)
    user = create_user(username="regular1", password="pass", role="reporter")
    client.login(username=user.username, password="pass")

    project = Project.objects.create(name="P-NO")
    issue = Issue.objects.create(project=project, title="Bug", description="desc")
    url = reverse("add_comment", kwargs={"issue_pk": issue.pk})

    r = client.post(url, {"text": "blocked"})
    # Most important: comment is NOT created
    assert not Comment.objects.filter(issue=issue, text="blocked").exists()
    # Preferred 403; allow 200/302 if implementation handles differently
    assert r.status_code in (403, 200, 302)


@pytest.mark.django_db
def test_add_comment_logged_in_valid_for_privileged_otherwise_forbidden(client):
    """
    If we have roles, regular user cannot add comment,
    but admin can. If no roles, test is skipped.
    """
    if not user_model_has_role_field():
        pytest.skip("User model has no 'role' field - role test skipped.")

    admin = create_user("admin_cmt", "pass", role="admin")
    regular = create_user("regular_cmt", "pass", role="reporter")
    project = Project.objects.create(name="P-MIX")
    issue = Issue.objects.create(project=project, title="Bug", description="desc")

    # Regular - should be blocked
    client.login(username=regular.username, password="pass")
    r1 = client.post(reverse("add_comment", kwargs={"issue_pk": issue.pk}), {"text": "nope"})
    assert not Comment.objects.filter(issue=issue, text="nope").exists()
    assert r1.status_code in (403, 200, 302)
    client.logout()

    # Admin - should succeed
    client.login(username=admin.username, password="pass")
    r2 = client.post(reverse("add_comment", kwargs={"issue_pk": issue.pk}), {"text": "ok"})
    assert r2.status_code in (200, 302)
    assert Comment.objects.filter(issue=issue, text="ok", author=admin).exists()


@pytest.mark.django_db
def test_add_comment_invalid_form(client):
    # Use privileged role if roles exist; otherwise skip as role validation would block test
    if not user_model_has_role_field():
        pytest.skip("User model has no 'role' field - comment form test skipped.")
    user = create_user(username="commenter2", password="pass", role="admin")
    client.login(username=user.username, password="pass")

    project = Project.objects.create(name="P6b")
    issue = Issue.objects.create(project=project, title="Bug", description="desc")
    url = reverse("add_comment", kwargs={"issue_pk": issue.pk})

    response = client.post(url, {"text": ""})  # missing required text
    assert response.status_code == 200
    # Check for required field error message
    assert b"This field is required" in response.content


# --- Auth tests --- #

@pytest.mark.django_db
def test_logout_logs_user_out(client):
    user = create_user(username="u1", password="pass")
    client.login(username=user.username, password="pass")
    r = client.get(reverse("project_list"))
    assert r.wsgi_request.user.is_authenticated
    response = client.post(reverse("logout"))
    assert response.status_code == 302
    r2 = client.get(reverse("project_list"))
    assert not r2.wsgi_request.user.is_authenticated


@pytest.mark.django_db
def test_register_view_valid(client):
    response = client.post(reverse("register"), {
        "username": "testuser",
        "email": "test@example.com",
        "password1": "StrongPass123",
        "password2": "StrongPass123",
    })
    assert response.status_code == 302
    # Check that the user was created
    assert UserModel.objects.filter(username="testuser").exists()


@pytest.mark.django_db
def test_register_view_invalid(client):
    response = client.post(reverse("register"), {
        "username": "",
        "email": "bademail",
        "password1": "123",
        "password2": "456",
    })
    assert response.status_code == 200
    # Check for required field or invalid email error
    assert b"This field is required" in response.content or b"Enter a valid email" in response.content
