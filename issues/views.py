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
    # Display a list of all projects, ordered by creation date (newest first)
    projects = Project.objects.all().order_by("-created_at")
    return render(request, "projects/list.html", {"projects": projects})


def project_detail(request, pk):
    # Show details for a single project, including its issues and issue creation form
    project = get_object_or_404(Project, pk=pk)
    issues = project.issues.select_related("author", "assignee").all()
    issue_form = IssueForm(user=request.user)
    return render(
        request,
        "projects/detail.html",
        {"project": project, "issue_form": issue_form, "issues": issues},
    )


def issue_detail(request, pk):
    # Show details for a single issue, including comments and comment form
    issue = get_object_or_404(Issue, pk=pk)
    comment_form = CommentForm()
    can_comment = request.user.is_authenticated and getattr(request.user, "role", "") in ("assignee", "admin")
    return render(
        request,
        "issues/detail.html",
        {"issue": issue, "comment_form": comment_form, "can_comment": can_comment},
    )


def issue_list(request):
    # Display a list of all issues, ordered by creation date (newest first)
    issues = Issue.objects.select_related("author", "assignee", "project").all().order_by("-created_at")
    return render(request, "issues/_issue_list.html", {"issues": issues})


@login_required
def create_issue(request, project_pk):
    # Create a new issue for a given project
    project = get_object_or_404(Project, pk=project_pk)
    if request.method == "POST":
        form = IssueForm(request.POST, user=request.user)
        if form.is_valid():
            issue = form.save(commit=False)
            issue.project = project
            issue.author = request.user

            # If admin, allow manual assignee selection, otherwise assign automatically
            if hasattr(request.user, "role") and request.user.role == "admin":
                assignee = form.cleaned_data.get("assignee")
                if assignee and hasattr(assignee, "role") and assignee.role == "assignee":
                    issue.assignee = assignee
                else:
                    # Assign to the assignee with the fewest assigned issues
                    assignee_auto = (
                        CustomUser.objects.filter(role="assignee", is_active=True)
                        .annotate(num_issues=Count("assigned_issues"))
                        .order_by("num_issues")
                        .first()
                    )
                    issue.assignee = assignee_auto
            else:
                # For non-admins, assign to the least loaded assignee (random if tie)
                assignees = (
                    CustomUser.objects.filter(role="assignee", is_active=True)
                    .annotate(num_issues=Count("assigned_issues"))
                )
                if assignees.exists():
                    min_count = assignees.order_by("num_issues").first().num_issues
                    candidates = assignees.filter(num_issues=min_count)
                    issue.assignee = candidates.order_by("?").first()

            issue.save()
            if request.headers.get("HX-Request"):
                # HTMX: return only the new issue item
                return render(request, "issues/_issue_item.html", {"issue": issue})
            return redirect("project_detail", pk=project.pk)
        else:
            # If form is invalid, re-render the project detail page with errors
            issues = project.issues.select_related("author", "assignee").all()
            return render(
                request,
                "projects/detail.html",
                {"project": project, "issue_form": form, "issues": issues},
            )
    return redirect("project_detail", pk=project.pk)


@login_required
def add_comment(request, issue_pk):
    # Add a comment to an issue (only for assignee or admin)
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
                # HTMX: return only the updated comments section
                return render(request, "issues/_comments_section.html", {"issue": issue, "keep_open": True})
            return redirect("issue_detail", pk=issue.pk)
        # If form is invalid, re-render issue detail with errors
        return render(request, "issues/detail.html", {"issue": issue, "comment_form": form, "keep_open": True})
    return redirect("issue_detail", pk=issue_pk)


@login_required
def change_status(request, pk):
    # Change the status of an issue (only for admin or assignee)
    issue = get_object_or_404(Issue, pk=pk)
    if not (hasattr(request.user, "role") and request.user.role in ("admin", "assignee")):
        return HttpResponseForbidden(_("Only assignees and admins can change status."))
    if request.method == "POST":
        new_status = request.POST.get("status")
        if new_status in dict(issue.STATUS_CHOICES):
            issue.status = new_status
            issue.save()
        if request.headers.get("HX-Request"):
            # HTMX: return only the status badge
            return render(request, "issues/_status_badge.html", {"issue": issue})
        return redirect("issues_list")
    else:
        return redirect("issue_detail", pk=pk)


@login_required
def create_project(request):
    # Create a new project (admin only)
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
    # User registration view
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("login")
    else:
        form = CustomUserCreationForm()
    return render(request, "auth/register.html", {"form": form})
