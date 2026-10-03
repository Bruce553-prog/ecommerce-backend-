"""
Authorization tests for the orders app.

Run with:
    python3 manage.py test orders.test_authorization -v 2

Alice and Bob are two ordinary customers. Every test checks that Alice
cannot see, change, cancel, pay for or use anything that belongs to Bob.
A response of 403 or 404 both count as "denied". A 200 (or a 500 crash)
means a real problem.
"""
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from .models import Order, ShippingAddress, PickupStation, Payment

User = get_user_model()
PASSWORD = 'Str0ng!Passw0rd#2026'


def make_user(name):
    return User.objects.create_user(
        username=name,
        email=f'{name}@example.com',
        password=PASSWORD,
    )


class OrderAuthorizationTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.alice = make_user('alice')
        cls.bob = make_user('bob')

        cls.station = PickupStation.objects.create(
            name='Test Station', location='CBD', city='Nairobi'
        )
        cls.alice_order = Order.objects.create(
            customer=cls.alice, pickup_station=cls.station, delivery_method='pickup'
        )
        cls.bob_order = Order.objects.create(
            customer=cls.bob, pickup_station=cls.station, delivery_method='pickup'
        )
        cls.bob_address = ShippingAddress.objects.create(
            customer=cls.bob, full_name='Bob Test', phone='0700000000',
            address_line1='1 Secret Street', city='Nairobi', country='Kenya',
        )
        cls.alice_address = ShippingAddress.objects.create(
            customer=cls.alice, full_name='Alice Test', phone='0711111111',
            address_line1='2 Alice Avenue', city='Nairobi', country='Kenya',
        )

    def setUp(self):
        self.client.force_authenticate(user=self.alice)

    def assertDenied(self, response):
        self.assertIn(
            response.status_code, (403, 404),
            f'Expected 403/404 but got {response.status_code}: {getattr(response, "data", "")}',
        )

    # ---------- Orders ----------

    def test_alice_can_see_her_own_order(self):
        r = self.client.get(f'/api/orders/orders/{self.alice_order.id}/detail_order/')
        self.assertEqual(r.status_code, 200)

    def test_alice_cannot_see_bobs_order(self):
        r = self.client.get(f'/api/orders/orders/{self.bob_order.id}/detail_order/')
        self.assertDenied(r)

    def test_my_orders_only_lists_alices_orders(self):
        r = self.client.get('/api/orders/orders/my_orders/')
        self.assertEqual(r.status_code, 200)
        ids = [o['id'] for o in r.data]
        self.assertIn(self.alice_order.id, ids)
        self.assertNotIn(self.bob_order.id, ids)

    def test_alice_cannot_cancel_bobs_order(self):
        r = self.client.post(f'/api/orders/orders/{self.bob_order.id}/cancel/')
        self.assertDenied(r)
        self.bob_order.refresh_from_db()
        self.assertEqual(self.bob_order.status, 'pending')

    def test_alice_can_cancel_her_own_order(self):
        r = self.client.post(f'/api/orders/orders/{self.alice_order.id}/cancel/')
        self.assertEqual(r.status_code, 200)
        self.alice_order.refresh_from_db()
        self.assertEqual(self.alice_order.status, 'cancelled')

    # ---------- Payments ----------

    @override_settings(SIMULATE_PAYMENTS=True)
    def test_alice_cannot_pay_for_bobs_order(self):
        r = self.client.post(
            '/api/orders/payments/initiate/',
            {'order_id': self.bob_order.id, 'payment_method': 'mpesa'},
            format='json',
        )
        self.assertDenied(r)
        self.assertFalse(Payment.objects.filter(order=self.bob_order).exists())
        self.bob_order.refresh_from_db()
        self.assertEqual(self.bob_order.status, 'pending')

    @override_settings(SIMULATE_PAYMENTS=True)
    def test_alice_can_pay_for_her_own_order(self):
        r = self.client.post(
            '/api/orders/payments/initiate/',
            {'order_id': self.alice_order.id, 'payment_method': 'mpesa'},
            format='json',
        )
        self.assertEqual(r.status_code, 201, getattr(r, 'data', ''))

    @override_settings(SIMULATE_PAYMENTS=False)
    def test_payment_is_switched_off_when_simulation_is_off(self):
        r = self.client.post(
            '/api/orders/payments/initiate/',
            {'order_id': self.alice_order.id, 'payment_method': 'mpesa'},
            format='json',
        )
        self.assertEqual(r.status_code, 503)
        self.assertFalse(Payment.objects.filter(order=self.alice_order).exists())

    # ---------- Shipping addresses ----------

    def test_address_list_only_contains_alices_addresses(self):
        r = self.client.get('/api/orders/shipping-addresses/')
        self.assertEqual(r.status_code, 200)
        results = r.data.get('results', r.data)
        ids = [a['id'] for a in results]
        self.assertIn(self.alice_address.id, ids)
        self.assertNotIn(self.bob_address.id, ids)

    def test_alice_cannot_read_bobs_address(self):
        r = self.client.get(f'/api/orders/shipping-addresses/{self.bob_address.id}/')
        self.assertDenied(r)

    def test_alice_cannot_edit_bobs_address(self):
        r = self.client.patch(
            f'/api/orders/shipping-addresses/{self.bob_address.id}/',
            {'full_name': 'Hacked'}, format='json',
        )
        self.assertDenied(r)
        self.bob_address.refresh_from_db()
        self.assertEqual(self.bob_address.full_name, 'Bob Test')

    def test_alice_cannot_delete_bobs_address(self):
        r = self.client.delete(f'/api/orders/shipping-addresses/{self.bob_address.id}/')
        self.assertDenied(r)
        self.assertTrue(ShippingAddress.objects.filter(pk=self.bob_address.pk).exists())

    def test_alice_cannot_set_bobs_address_as_default(self):
        r = self.client.post(f'/api/orders/shipping-addresses/{self.bob_address.id}/set_default/')
        self.assertDenied(r)

    def test_new_address_always_belongs_to_the_logged_in_user(self):
        r = self.client.post(
            '/api/orders/shipping-addresses/',
            {
                'full_name': 'Alice New', 'phone': '0722222222',
                'address_line1': '3 New Road', 'city': 'Nairobi', 'country': 'Kenya',
                'customer': self.bob.id,  # attempt to plant it on Bob's account
            },
            format='json',
        )
        self.assertEqual(r.status_code, 201, getattr(r, 'data', ''))
        created = ShippingAddress.objects.get(pk=r.data['id'])
        self.assertEqual(created.customer_id, self.alice.id)

    # ---------- Checkout ----------

    def test_alice_cannot_check_out_with_bobs_address(self):
        before = Order.objects.filter(customer=self.alice).count()
        r = self.client.post(
            '/api/orders/orders/checkout/',
            {'delivery_method': 'delivery', 'shipping_address_id': self.bob_address.id},
            format='json',
        )
        self.assertEqual(r.status_code, 400, getattr(r, 'data', ''))
        self.assertEqual(Order.objects.filter(customer=self.alice).count(), before)

    # ---------- Not logged in ----------

    def test_anonymous_user_is_rejected_everywhere_private(self):
        self.client.force_authenticate(user=None)
        checks = [
            ('get', '/api/orders/orders/my_orders/'),
            ('get', f'/api/orders/orders/{self.alice_order.id}/detail_order/'),
            ('post', f'/api/orders/orders/{self.alice_order.id}/cancel/'),
            ('get', '/api/orders/cart/my_cart/'),
            ('get', '/api/orders/shipping-addresses/'),
            ('post', '/api/orders/orders/checkout/'),
            ('post', '/api/orders/payments/initiate/'),
        ]
        for method, url in checks:
            r = getattr(self.client, method)(url)
            self.assertEqual(r.status_code, 401, f'{method.upper()} {url} returned {r.status_code}')