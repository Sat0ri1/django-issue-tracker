from django.contrib import admin
from .models import Project, Issue, Comment

# Register your models here.
admin.site.register(Project)
admin.site.register(Issue)
admin.site.register(Comment)