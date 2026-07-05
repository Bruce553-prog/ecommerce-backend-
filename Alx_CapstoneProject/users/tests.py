from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

User = get_user_model()


class AuthAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user1",
            email="user@test.com",
            password="TestPass123!"
        )

    def test_user_can_register(self):
        response = self.client.post('/api/users/register/', {
            'username': 'newuser',
            'email': 'new@test.com',
            'password': 'TestPass123!',
            'password2': 'TestPass123!',
            'phone': '0712345678'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_duplicate_email_rejected(self):
        response = self.client.post('/api/users/register/', {
            'username': 'user2',
            'email': 'user@test.com',  # already exists
            'password': 'TestPass123!',
            'password2': 'TestPass123!',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_mismatch_rejected(self):
        response = self.client.post('/api/users/register/', {
            'username': 'user3',
            'email': 'user3@test.com',
            'password': 'TestPass123!',
            'password2': 'WrongPass123!',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_can_login(self):
        response = self.client.post('/api/users/login/', {
            'email': 'user@test.com',
            'password': 'TestPass123!'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_user_can_view_profile(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/users/users/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'user@test.com')

    def test_unauthenticated_cannot_view_profile(self):
        response = self.client.get('/api/users/users/me/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_cannot_access_admin_endpoint(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/users/admin/users/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

