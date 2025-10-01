from django.urls import path
from . import views

urlpatterns = [
    path("", views.project_list, name="project_list"),
    path("projects/<int:pk>/", views.project_detail, name="project_detail"),
    path("projects/create/", views.create_project, name="create_project"),
    path("projects/<int:project_pk>/issues/create/", views.create_issue, name="create_issue"),
    path("issues/<int:pk>/", views.issue_detail, name="issue_detail"),
    path("issues/<int:pk>/change-status/", views.change_status, name="change_status"),
    path("issues/<int:issue_pk>/comments/add/", views.add_comment, name="add_comment"),
    path("issues/", views.issue_list, name="issues_list"),
    path('projects/<int:pk>/issues/', views.project_issues_list, name='project_issues_list'),
]