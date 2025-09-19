from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from .models import Project, Issue, Comment  # noqa: F401
from .forms import IssueForm, CommentForm


def project_list(request):
    projects = Project.objects.all().order_by("-created_at")
    return render(request, "projects/list.html", {"projects": projects})


def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)
    issue_form = IssueForm()
    return render(request, "projects/detail.html", {"project": project, "issue_form": issue_form})


def issue_detail(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    comment_form = CommentForm()
    return render(request, "issues/detail.html", {"issue": issue, "comment_form": comment_form})


@login_required
def create_issue(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if request.method == "POST":
        form = IssueForm(request.POST)
        if form.is_valid():
            issue = form.save(commit=False)
            issue.project = project
            issue.author = request.user
            issue.save()
            # HTMX fragment
            if request.headers.get("HX-Request"):
                return render(request, "issues/_issue_item.html", {"issue": issue})
            return redirect("project_detail", pk=project.pk)
        return render(request, "projects/detail.html", {"project": project, "issue_form": form})
    return redirect("project_detail", pk=project.pk)


@login_required
def add_comment(request, issue_pk):
    issue = get_object_or_404(Issue, pk=issue_pk)
    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.issue = issue
            comment.author = request.user
            comment.save()
            # HTMX fragment
            if request.headers.get("HX-Request"):
                return render(request, "issues/_comment_item.html", {"comment": comment})
            return redirect("issue_detail", pk=issue.pk)
        return render(request, "issues/detail.html", {"issue": issue, "comment_form": form})
    return redirect("issue_detail", pk=issue.pk)


@login_required
def change_status(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    if request.method == "POST":
        new_status = request.POST.get("status")
        if new_status in dict(Issue.STATUS_CHOICES):
            issue.status = new_status
            issue.save()
            # HTMX fragment
            if request.headers.get("HX-Request"):
                return render(request, "issues/_issue_item.html", {"issue": issue})
            return redirect("project_detail", pk=issue.project.pk)
    return HttpResponse(status=400)


def register(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("project_list")
        return render(request, "auth/register.html", {"form": form})
    form = UserCreationForm()
    return render(request, "auth/register.html", {"form": form})
