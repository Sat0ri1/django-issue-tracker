from django import forms
from .models import Issue, Comment

class IssueForm(forms.ModelForm):
    class Meta:
        model = Issue
        fields = ["title", "description", "assignee"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(attrs={"rows": 2}),
        }