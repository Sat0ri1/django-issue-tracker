import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from issues.models import Project, Issue, Comment

UserModel = get_user_model()


def user_model_has_role_field() -> bool:
    return any(getattr(f, "name", "") == "role" for f in UserModel._meta.get_fields())


def create_user(username: str, password: str, role: str | None = None):
    if role and user_model_has_role_field():
        return UserModel.objects.create_user(username=username, password=password, role=role)
    return UserModel.objects.create_user(username=username, password=password)


@pytest.mark.django_db
class TestHTMXViews:

    @pytest.fixture
    def admin_user(self):
        return create_user("admin", "password123", role="admin")

    @pytest.fixture  
    def assignee_user(self):
        return create_user("assignee", "password123", role="assignee")
    
    @pytest.fixture
    def regular_user(self):
        return create_user("reporter", "password123", role="reporter")

    @pytest.fixture
    def user(self):
        # fallback for tests that don't need roles - ale daj rolę jeśli potrzebna
        role = "admin" if user_model_has_role_field() else None
        return create_user("alice", "password123", role=role)

    @pytest.fixture
    def project(self):
        return Project.objects.create(name="Test Project")

    @pytest.fixture
    def issue(self, project, user):
        return Issue.objects.create(
            project=project, title="Bug #1", description="Bug description", author=user
        )

    # ---------------------------
    # create_issue
    # ---------------------------
    def test_create_issue_requires_login(self, client, project):
        url = reverse("create_issue", kwargs={"project_pk": project.pk})
        r = client.post(url, {"title": "HTMX Bug", "description": "desc"}, HTTP_HX_REQUEST="true")
        # niezalogowany → przekierowanie na login
        assert r.status_code == 302
        assert "/login/" in r.url

    def test_create_issue_logged_in(self, client, user, project):
        client.login(username="alice", password="password123")
        url = reverse("create_issue", kwargs={"project_pk": project.pk})
        data = {"title": "HTMX Bug", "description": "desc"}
        r = client.post(url, data, HTTP_HX_REQUEST="true")
        assert r.status_code == 200
        # Issue faktycznie dodane
        assert project.issues.filter(title="HTMX Bug").exists()
        assert b"HTMX Bug" in r.content

    # ---------------------------
    # add_comment - ROLE TESTS
    # ---------------------------
    def test_add_comment_requires_login(self, client, issue):
        url = reverse("add_comment", kwargs={"issue_pk": issue.pk})
        r = client.post(url, {"text": "New comment"}, HTTP_HX_REQUEST="true")
        assert r.status_code == 302
        assert "/login/" in r.url

    @pytest.mark.parametrize("role,username", [("admin", "admin"), ("assignee", "assignee")])
    def test_add_comment_allowed_for_privileged_roles_htmx(self, client, issue, role, username):
        if not user_model_has_role_field():
            pytest.skip("User model has no 'role' field - role test skipped.")
        
        user = create_user(username, "password123", role=role)
        client.login(username=username, password="password123")
        url = reverse("add_comment", kwargs={"issue_pk": issue.pk})
        
        # HTMX request
        r = client.post(url, {"text": f"Comment by {role}"}, HTTP_HX_REQUEST="true")
        assert r.status_code == 200
        
        # Comment created
        assert Comment.objects.filter(issue=issue, text=f"Comment by {role}", author=user).exists()
        
        # HTMX response contains updated comments section
        content = r.content.decode("utf-8")
        assert f"Comment by {role}" in content
        assert "Comments (" in content  # updated count
        assert 'id="comments-section-' in content  # returns comments section
        assert "open" in content  # section stays open (keep_open=True)

    def test_add_comment_forbidden_for_regular_user_htmx(self, client, issue):
        if not user_model_has_role_field():
            pytest.skip("User model has no 'role' field - role test skipped.")
        
        user = create_user("reporter", "password123", role="reporter")
        client.login(username="reporter", password="password123")
        url = reverse("add_comment", kwargs={"issue_pk": issue.pk})
        
        r = client.post(url, {"text": "Blocked comment"}, HTTP_HX_REQUEST="true")
        
        # Comment NOT created
        assert not Comment.objects.filter(issue=issue, text="Blocked comment").exists()
        
        # Should return 403 or handle gracefully
        assert r.status_code in (403, 200, 302)

    def test_add_comment_htmx_updates_count_and_stays_open(self, client, issue):
        if not user_model_has_role_field():
            pytest.skip("User model has no 'role' field - role test skipped.")
        
        admin = create_user("admin_test", "password123", role="admin")
        client.login(username="admin_test", password="password123")
        url = reverse("add_comment", kwargs={"issue_pk": issue.pk})
        
        # Add first comment
        r1 = client.post(url, {"text": "First comment"}, HTTP_HX_REQUEST="true")
        assert r1.status_code == 200
        content1 = r1.content.decode("utf-8")
        assert "Comments (1)" in content1
        assert "First comment" in content1
        assert "open" in content1
        
        # Add second comment
        r2 = client.post(url, {"text": "Second comment"}, HTTP_HX_REQUEST="true")
        assert r2.status_code == 200
        content2 = r2.content.decode("utf-8")
        assert "Comments (2)" in content2
        assert "Second comment" in content2
        assert "First comment" in content2  # previous comment still there
        assert "open" in content2  # still open

    def test_add_comment_htmx_with_enter_trigger(self, client, issue):
        """
        Test that simulates Enter key submission (hx-trigger includes keyup)
        """
        if not user_model_has_role_field():
            pytest.skip("User model has no 'role' field - role test skipped.")
        
        admin = create_user("admin_enter", "password123", role="admin")
        client.login(username="admin_enter", password="password123")
        url = reverse("add_comment", kwargs={"issue_pk": issue.pk})
        
        # Simulate Enter key trigger (HTMX would send this)
        headers = {
            "HTTP_HX_REQUEST": "true",
            "HTTP_HX_TRIGGER": "keyup"  # simulating Enter key trigger
        }
        
        r = client.post(url, {"text": "Comment via Enter"}, **headers)
        assert r.status_code == 200
        
        # Comment created
        assert Comment.objects.filter(issue=issue, text="Comment via Enter").exists()
        
        # Response contains updated section
        content = r.content.decode("utf-8")
        assert "Comment via Enter" in content
        assert "open" in content

    def test_add_comment_invalid_form_htmx(self, client, issue):
        if not user_model_has_role_field():
            pytest.skip("User model has no 'role' field - role test skipped.")
        
        admin = create_user("admin_invalid", "password123", role="admin")
        client.login(username="admin_invalid", password="password123")
        url = reverse("add_comment", kwargs={"issue_pk": issue.pk})
        
        # Empty text (invalid)
        r = client.post(url, {"text": ""}, HTTP_HX_REQUEST="true")
        assert r.status_code == 200
        
        # No comment created
        assert not Comment.objects.filter(issue=issue, text="").exists()
        
        # Should show form errors (depending on implementation)
        content = r.content.decode("utf-8")
        # Either shows error message or re-renders form
        assert "Comments (" in content  # still shows comments section

    # ---------------------------
    # change_status
    # ---------------------------
    def test_change_status_requires_login(self, client, issue):
        url = reverse("change_status", kwargs={"pk": issue.pk})
        r = client.post(url, {"status": "in_progress"}, HTTP_HX_REQUEST="true")
        assert r.status_code == 302
        assert "/login/" in r.url

    def test_change_status_logged_in(self, client, user, issue):
        client.login(username="alice", password="password123")
        url = reverse("change_status", kwargs={"pk": issue.pk})
        r = client.post(url, {"status": "in_progress"}, HTTP_HX_REQUEST="true")
        assert r.status_code == 200
        issue.refresh_from_db()
        assert issue.status == "in_progress"
        # fragment HTMX zawiera tytuł issue
        assert bytes(issue.title, encoding="utf-8") in r.content

    @pytest.mark.parametrize("role", ["admin", "assignee"])
    def test_change_status_allowed_for_privileged_roles_htmx(self, client, issue, role):
        if not user_model_has_role_field():
            pytest.skip("User model has no 'role' field - role test skipped.")
        
        user = create_user(f"user_{role}", "password123", role=role)
        client.login(username=f"user_{role}", password="password123")
        url = reverse("change_status", kwargs={"pk": issue.pk})
        
        r = client.post(url, {"status": "done"}, HTTP_HX_REQUEST="true")
        assert r.status_code == 200
        
        issue.refresh_from_db()
        assert issue.status == "done"
        
        # HTMX returns updated issue item
        content = r.content.decode("utf-8")
        assert issue.title in content
        assert "Done" in content or "done" in content

    def test_change_status_forbidden_for_regular_user_htmx(self, client, issue):
        if not user_model_has_role_field():
            pytest.skip("User model has no 'role' field - role test skipped.")
        
        user = create_user("reporter_status", "password123", role="reporter")
        client.login(username="reporter_status", password="password123")
        url = reverse("change_status", kwargs={"pk": issue.pk})
        
        original_status = issue.status
        r = client.post(url, {"status": "done"}, HTTP_HX_REQUEST="true")
        
        # Status should NOT change
        issue.refresh_from_db()
        assert issue.status == original_status
        
        # Should return error or handle gracefully
        assert r.status_code in (403, 200, 302)
