from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from products.models import Category, Product
from .models import Cart, CartItem, Order, ShippingAddress

User = get_user_model()


class CartAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user1",
            email="user@test.com",
            password="TestPass123!"
        )
        self.category = Category.objects.create(name="Electronics")
        self.product = Product.objects.create(
            name="Samsung Galaxy",
            description="A smartphone",
            price=500.00,
            stock=10,
            category=self.category
        )
        self.client.force_authenticate(user=self.user)

    def test_unauthenticated_cannot_access_cart(self):
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/orders/cart/my_cart/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_view_cart(self):
        response = self.client.get('/api/orders/cart/my_cart/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_can_add_item_to_cart(self):
        response = self.client.post('/api/orders/cart/add_item/', {
            'product_id': self.product.id,
            'quantity': 2
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_cart_quantity_cannot_be_zero(self):
        response = self.client.post('/api/orders/cart/add_item/', {
            'product_id': self.product.id,
            'quantity': 0
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class OrderAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user1",
            email="user@test.com",
            password="TestPass123!"
        )
        self.category = Category.objects.create(name="Electronics")
        self.product = Product.objects.create(
            name="Samsung Galaxy",
            description="A smartphone",
            price=500.00,
            stock=10,
            category=self.category
        )
        self.address = ShippingAddress.objects.create(
            customer=self.user,
            full_name="Test User",
            phone="0712345678",
            address_line1="123 Test St",
            city="Nairobi",
            country="Kenya"
        )
        self.client.force_authenticate(user=self.user)

    def test_user_can_view_orders(self):
        response = self.client.get('/api/orders/orders/my_orders/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_checkout_with_empty_cart(self):
        response = self.client.post('/api/orders/orders/checkout/', {
            'shipping_address_id': self.address.id
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_stock_reduces_after_order(self):
        # Add item to cart
        cart = Cart.objects.create(customer=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=3)

        # Checkout
        self.client.post('/api/orders/orders/checkout/', {
            'shipping_address_id': self.address.id
        })

        # Check stock reduced
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 7)

    def test_cannot_order_more_than_stock(self):
        cart = Cart.objects.create(customer=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=100)

        response = self.client.post('/api/orders/orders/checkout/', {
            'shipping_address_id': self.address.id
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

