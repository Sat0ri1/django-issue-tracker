from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django.conf import settings

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('admin', _("Administrator")),
        ('assignee', _("Assignee")),
        ('reporter', _("Reporter")),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='reporter')

# --- Superuser is always admin ---
@receiver(post_save, sender=CustomUser)
def set_role_for_superuser(sender, instance, created, **kwargs):
    if created and instance.is_superuser and instance.role != "admin":
        instance.role = "admin"
        instance.save()

class Project(models.Model):
    """Project where issues are created"""
    name = models.CharField(max_length=100, verbose_name=_("Project name"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created at"))

    def __str__(self):
        return self.name

class Issue(models.Model):
    """Single issue in a project"""
    STATUS_CHOICES = [
        ("todo", _("To Do")),
        ("in_progress", _("In Progress")),
        ("done", _("Done")),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="issues", verbose_name=_("Project"))
    title = models.CharField(max_length=200, verbose_name=_("Title"))
    description = models.TextField(verbose_name=_("Description"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="todo", verbose_name=_("Status"))
    assignee = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_issues", verbose_name=_("Assignee")
    )
    author = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_issues", verbose_name=_("Author")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created at"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated at"))

    def __str__(self):
        return f"[{self.get_status_display()}] {self.title}"

class Comment(models.Model):
    """Comments for issues"""
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='authored_comments'
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.author.username} on {self.issue.title}"
