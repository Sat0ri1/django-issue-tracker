from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils.translation import gettext as _
from .models import Project, Issue
from .forms import IssueForm, CommentForm, ProjectForm, CustomUserCreationForm

CustomUser = get_user_model()


def project_list(request):
    projects = Project.objects.all().order_by("-created_at")
    return render(request, "projects/list.html", {"projects": projects})


def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)
    issues = project.issues.select_related("author", "assignee").all()
    issue_form = IssueForm(user=request.user)
    return render(
        request,
        "projects/detail.html",
        {"project": project, "issue_form": issue_form, "issues": issues},
    )


def issue_detail(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    comment_form = CommentForm()
    can_comment = request.user.is_authenticated and getattr(request.user, "role", "") in ("assignee", "admin")
    return render(
        request,
        "issues/detail.html",
        {"issue": issue, "comment_form": comment_form, "can_comment": can_comment},
    )


def issue_list(request):
    issues = Issue.objects.select_related("author", "assignee", "project").all().order_by("-created_at")
    return render(request, "issues/list.html", {"issues": issues})


@login_required
def create_issue(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if request.method == "POST":
        form = IssueForm(request.POST, user=request.user)
        if form.is_valid():
            issue = form.save(commit=False)
            issue.project = project
            issue.author = request.user

            print(f"DEBUG: User role: {getattr(request.user, 'role', 'NO ROLE')}")

            # Assignee selection logic
            if hasattr(request.user, "role") and request.user.role == "admin":
                print("DEBUG: Admin path")
                # Admin can choose assignee from form, but only assignees
                assignee = form.cleaned_data.get('assignee')
                print(f"DEBUG: Form assignee: {assignee}")

                # Check if admin selected a valid assignee
                if assignee and assignee != "" and hasattr(assignee, 'role') and assignee.role == "assignee":
                    issue.assignee = assignee
                    print(f"DEBUG: Manually assigned to: {assignee}")
                else:
                    # Admin did not select or selected invalid assignee - auto-assignment
                    print("DEBUG: Admin fallback to auto-assignment")
                    assignee_auto = CustomUser.objects.filter(role='assignee', is_active=True).annotate(
                        num_issues=Count('assigned_issues')
                    ).order_by('num_issues').first()
                    issue.assignee = assignee_auto
                    print(f"DEBUG: Auto-assigned to: {assignee_auto}")
            else:
                print("DEBUG: Non-admin path")
                # For non-admin, assign assignee with least issues (random if tie)
                assignees = CustomUser.objects.filter(role='assignee', is_active=True).annotate(
                    num_issues=Count('assigned_issues')
                )
                print(f"DEBUG: Available assignees: {list(assignees.values('username', 'num_issues'))}")
                if assignees.exists():
                    # Find minimum number of issues
                    min_count = assignees.order_by('num_issues').first().num_issues
                    print(f"DEBUG: Min count: {min_count}")
                    # Select all with minimum and randomly pick one
                    candidates = assignees.filter(num_issues=min_count)
                    print(f"DEBUG: Candidates: {list(candidates.values('username', 'num_issues'))}")
                    issue.assignee = candidates.order_by('?').first()
                    print(f"DEBUG: Selected assignee: {issue.assignee}")
                else:
                    print("DEBUG: No assignees available")

            print(f"DEBUG: Final assignee: {issue.assignee}")
            issue.save()
            if request.headers.get("HX-Request"):
                return render(request, "issues/_issue_item.html", {"issue": issue})
            return redirect("project_detail", pk=project.pk)
        else:
            # Form error - use existing project detail template with errors
            issues = project.issues.select_related("author", "assignee").all()
            return render(request, "projects/detail.html", {
                "project": project, 
                "issue_form": form, 
                "issues": issues
            })
    else:
        form = IssueForm(user=request.user)
    # GET request - redirect to project detail
    return redirect("project_detail", pk=project.pk)


@login_required
def add_comment(request, issue_pk):
    issue = get_object_or_404(Issue, pk=issue_pk)
    if not (hasattr(request.user, "role") and request.user.role in ("assignee", "admin")):
        return HttpResponseForbidden(_("Only assignees and admins can comment."))
    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.issue = issue
            comment.author = request.user
            comment.save()
            if request.headers.get("HX-Request"):
                return render(request, "issues/_comments_section.html", {"issue": issue, "keep_open": True})
            return redirect("issue_detail", pk=issue.pk)
        # Fallback with errors
        ctx = {"issue": issue, "comment_form": form, "keep_open": True}
        return render(request, "issues/detail.html", ctx)
    return redirect("issue_detail", pk=issue.pk)


@login_required
def change_status(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    # Dodaj sprawdzenie roli!
    if not (hasattr(request.user, "role") and request.user.role in ("admin", "assignee")):
        return HttpResponseForbidden(_("Only assignees and admins can change status."))
    if request.method == "POST":
        new_status = request.POST.get("status")
        if new_status in dict(issue.STATUS_CHOICES):
            issue.status = new_status
            issue.save()
        if request.headers.get("HX-Request"):
            return render(request, "issues/_issue_item.html", {"issue": issue})
        return redirect("issues_list")


@login_required
def create_project(request):
    # Only admin can add projects
    if not (hasattr(request.user, "role") and request.user.role == "admin"):
        return HttpResponseForbidden(_("Only admin can add projects."))
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("project_list")
    else:
        form = ProjectForm()
    return render(request, "projects/create.html", {"form": form})


def register(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("login")
    else:
        form = CustomUserCreationForm()
    return render(request, "auth/register.html", {"form": form})
