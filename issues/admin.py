from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Project, Issue, Comment, CustomUser

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ("username", "email", "role", "is_active", "is_staff")
    fieldsets = UserAdmin.fieldsets + (
        ("Role info", {"fields": ("role",)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Role info", {"fields": ("role",)}),
    )

admin.site.register(Project)
admin.site.register(Issue)
admin.site.register(Comment)
admin.site.register(CustomUser, CustomUserAdmin)