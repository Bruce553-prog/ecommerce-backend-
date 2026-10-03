"""
Role and privilege tests for the users app.

Run with:
    python3 manage.py test users.test_authorization -v 2

Checks that a customer or vendor cannot reach admin endpoints, cannot make
themselves a vendor or admin, and that account deletion needs the password.
"""
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

User = get_user_model()
PASSWORD = 'Str0ng!Passw0rd#2026'


def make_user(name, **extra):
    user = User.objects.create_user(
        username=name,
        email=f'{name}@example.com',
        password=PASSWORD,
    )
    for field, value in extra.items():
        setattr(user, field, value)
    if extra:
        user.save()
    return user


class RoleAuthorizationTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.customer = make_user('customer')
        cls.other = make_user('other')
        cls.vendor = make_user('vendor', is_vendor=True)
        cls.admin = make_user('admin', is_staff=True, is_superuser=True)

    def assertDenied(self, response):
        self.assertIn(
            response.status_code, (403, 404),
            f'Expected 403/404 but got {response.status_code}: {getattr(response, "data", "")}',
        )

    # ---------- Admin endpoints ----------

    def test_anonymous_cannot_use_admin_endpoints(self):
        r = self.client.get('/api/users/admin/users/')
        self.assertEqual(r.status_code, 401)

    def test_customer_cannot_list_users(self):
        self.client.force_authenticate(user=self.customer)
        r = self.client.get('/api/users/admin/users/')
        self.assertEqual(r.status_code, 403)

    def test_vendor_cannot_list_users(self):
        self.client.force_authenticate(user=self.vendor)
        r = self.client.get('/api/users/admin/users/')
        self.assertEqual(r.status_code, 403)

    def test_customer_cannot_edit_another_user_through_admin_endpoint(self):
        self.client.force_authenticate(user=self.customer)
        r = self.client.patch(
            f'/api/users/admin/users/{self.other.id}/',
            {'username': 'hacked'}, format='json',
        )
        self.assertEqual(r.status_code, 403)
        self.other.refresh_from_db()
        self.assertEqual(self.other.username, 'other')

    def test_customer_cannot_delete_another_user_through_admin_endpoint(self):
        self.client.force_authenticate(user=self.customer)
        r = self.client.delete(f'/api/users/admin/users/{self.other.id}/')
        self.assertEqual(r.status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.other.pk).exists())

    def test_customer_cannot_grant_vendor_status(self):
        self.client.force_authenticate(user=self.customer)
        r = self.client.post(f'/api/users/admin/users/{self.customer.id}/toggle_vendor/')
        self.assertEqual(r.status_code, 403)
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_vendor)

    def test_admin_can_list_users(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.get('/api/users/admin/users/')
        self.assertEqual(r.status_code, 200)

    def test_admin_can_toggle_vendor(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.post(f'/api/users/admin/users/{self.customer.id}/toggle_vendor/')
        self.assertEqual(r.status_code, 200)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_vendor)

    # ---------- Privilege escalation by editing the request ----------

    def test_customer_cannot_make_themselves_vendor_or_admin_via_profile_update(self):
        self.client.force_authenticate(user=self.customer)
        r = self.client.patch(
            '/api/users/users/update_profile/',
            {
                'username': 'customer_renamed',
                'is_vendor': True,
                'is_staff': True,
                'is_superuser': True,
            },
            format='json',
        )
        self.assertEqual(r.status_code, 200, getattr(r, 'data', ''))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.username, 'customer_renamed')  # normal field still works
        self.assertFalse(self.customer.is_vendor)
        self.assertFalse(self.customer.is_staff)
        self.assertFalse(self.customer.is_superuser)

    def test_registration_ignores_role_fields(self):
        r = self.client.post(
            '/api/users/register/',
            {
                'username': 'sneaky',
                'email': 'sneaky@example.com',
                'password': PASSWORD,
                'password2': PASSWORD,
                'phone': '0700000001',
                'is_staff': True,
                'is_superuser': True,
                'is_vendor': True,
            },
            format='json',
        )
        self.assertEqual(r.status_code, 201, getattr(r, 'data', ''))
        user = User.objects.get(email='sneaky@example.com')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_vendor)

    # ---------- Own account only ----------

    def test_me_returns_only_the_logged_in_user(self):
        self.client.force_authenticate(user=self.customer)
        r = self.client.get('/api/users/users/me/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['email'], self.customer.email)

    def test_me_requires_login(self):
        r = self.client.get('/api/users/users/me/')
        self.assertEqual(r.status_code, 401)

    def test_delete_account_needs_the_password(self):
        self.client.force_authenticate(user=self.customer)
        r = self.client.delete('/api/users/users/delete_account/', {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_active)

    def test_delete_account_rejects_wrong_password(self):
        self.client.force_authenticate(user=self.customer)
        r = self.client.delete(
            '/api/users/users/delete_account/', {'password': 'wrong-password'}, format='json'
        )
        self.assertEqual(r.status_code, 400)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_active)