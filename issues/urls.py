from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("", views.project_list, name="project_list"),
    path("projects/<int:pk>/", views.project_detail, name="project_detail"),
    path("projects/<int:project_pk>/issues/create/", views.create_issue, name="create_issue"),
    path("issues/<int:pk>/", views.issue_detail, name="issue_detail"),
    path("issues/<int:pk>/change-status/", views.change_status, name="change_status"),
    path("issues/<int:issue_pk>/comments/add/", views.add_comment, name="add_comment"),
    path("login/", auth_views.LoginView.as_view(template_name="auth/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="/"), name="logout"),
    path("register/", views.register, name="register"),
]