from django import forms
from django.contrib.auth import get_user_model
from .models import Issue, Comment, Project
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _

User = get_user_model()

class IssueForm(forms.ModelForm):
    class Meta:
        model = Issue
        fields = ["title", "description", "assignee"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "title": _("Title"),
            "description": _("Description"),
            "assignee": _("Assignee"),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and hasattr(user, "role") and user.role != "admin":
            self.fields.pop("assignee", None)
        else:
            self.fields["assignee"].queryset = User.objects.filter(role="assignee", is_active=True)

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {
            "text": _("Comment"),
        }

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label=_("Email"))

    class Meta:
        model = get_user_model()
        fields = ("username", "email", "password1", "password2")
        labels = {
            "username": _("Username"),
            "email": _("Email"),
            "password1": _("Password"),
            "password2": _("Repeat password"),
        }

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "description"]
        labels = {
            "name": _("Project name"),
            "description": _("Description"),
        }