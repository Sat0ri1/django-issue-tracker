import pytest
from django.test import Client
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.mark.django_db
class TestAuthViews:
    def setup_method(self):
        self.client = Client()

    def test_register_view_get(self):
        response = self.client.get(reverse('register'))
        assert response.status_code == 200
        assert b'Register' in response.content or b'Rejestracja' in response.content

    def test_register_view_post_valid(self):
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'complexpass123',
            'password2': 'complexpass123',
            'role': 'user'
        })
        assert response.status_code == 302  # Redirect to login
        assert User.objects.filter(username='newuser').exists()

    def test_register_view_post_invalid(self):
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'invalid-email',
            'password1': 'pass123',
            'password2': 'different'
        })
        assert response.status_code == 200  # Stay on form with errors
        assert not User.objects.filter(username='newuser').exists()

    def test_login_view(self):
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpass123'
        })
        assert response.status_code == 302  # Redirect after login

    def test_protected_views_require_login(self):
        # Test create_issue requires login
        response = self.client.get(reverse('create_issue', kwargs={'project_pk': 1}))
        assert response.status_code == 302  # Redirect to login
        
        # Test add_comment requires login
        response = self.client.get(reverse('add_comment', kwargs={'issue_pk': 1}))
        assert response.status_code == 302  # Redirect to login

    def test_role_based_permissions(self):
        admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            role='admin'
        )
        user = User.objects.create_user(
            username='user',
            email='user@example.com',
            password='userpass123',
            role='user'
        )
        
        # Admin can create projects
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('create_project'))
        assert response.status_code == 200
        
        # Regular user cannot create projects
        self.client.login(username='user', password='userpass123')
        response = self.client.get(reverse('create_project'))
        assert response.status_code == 403