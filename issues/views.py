from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils.translation import gettext as _
from .models import Project, Issue, Comment 
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
    
    # Add comments for each issue
    for issue in issues:
        issue.comments_list = Comment.objects.filter(issue=issue).select_related('author').all()
    
    issue_form = IssueForm(user=request.user)
    return render(
        request,
        "projects/detail.html",
        {"project": project, "issue_form": issue_form, "issues": issues},
    )


def project_issues_list(request, pk):
    # Return only the issues list for a specific project (for HTMX refresh)
    project = get_object_or_404(Project, pk=pk)
    issues = (
        project.issues
        .select_related("author", "assignee")
        .prefetch_related("comments__author")
        .all()
    )
    return render(request, "issues/_issue_list.html", {"project": project, "issues": issues})


def issue_detail(request, pk):
    # Show details for a single issue, including comments and comment form
    issue = get_object_or_404(Issue, pk=pk)
    # Use Comment.objects.filter instead of issue.comment
    comments = Comment.objects.filter(issue=issue).select_related('author').all()
    comment_form = CommentForm()
    can_comment = request.user.is_authenticated and getattr(request.user, "role", "") in ("assignee", "admin")
    return render(
        request,
        "issues/detail.html",
        {
            "issue": issue, 
            "comments": comments,
            "comment_form": comment_form, 
            "can_comment": can_comment
        },
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
                # HTMX: return clean form after successful creation with trigger for list refresh
                clean_form = IssueForm(user=request.user)
                response = render(request, "issues/_issue_form.html", {
                    "issue_form": clean_form,
                    "project": project,
                    "user": request.user,
                })
                # Add custom header to trigger issues list refresh
                response['HX-Trigger'] = 'issueCreated'
                return response
            return redirect("project_detail", pk=project.pk)
        else:
            if request.headers.get("HX-Request"):
                # HTMX: return form with validation errors
                return render(request, "issues/_issue_form.html", {
                    "issue_form": form,
                    "project": project,
                    "user": request.user,
                })
            else:
                issues = project.issues.select_related("author", "assignee").all()
                return render(
                    request,
                    "projects/detail.html",
                    {"project": project, "issue_form": form, "issues": issues},
                )
    return redirect("project_detail", pk=project.pk)


@login_required
def add_comment(request, issue_pk):
    issue = get_object_or_404(Issue, pk=issue_pk)

    if not (hasattr(request.user, "role") and request.user.role in ("assignee", "admin")):
        return HttpResponseForbidden(_("Only assignees and admins can comment."))

    if request.method == "POST":
        text = request.POST.get("content", "").strip()
        if text:
            comment = Comment.objects.create(issue=issue, author=request.user, text=text)

            if request.headers.get("HX-Request"):
                # Count current number of comments
                count = Comment.objects.filter(issue=issue).count()
                # Render single comment + data for OOB (counter and remove "No comments")
                response = render(
                    request,
                    "issues/_comment_item.html",
                    {
                        "comment": comment,
                        "issue": issue,
                        "oob_count": count,      # used in _comment_item.html for hx-swap-oob
                    }
                )
                return response

        # Empty text with HTMX – no changes
        if request.headers.get("HX-Request"):
            return HttpResponse(status=204)

    return redirect("project_detail", pk=issue.project.pk)


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
        # No-JS fallback: redirect to issue detail (full page with layout)
        return redirect("issue_detail", pk=pk)
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
