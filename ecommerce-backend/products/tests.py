from django.test import TestCase
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from .models import Category, Product

User = get_user_model()


class CategoryModelTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Electronics",
            description="Electronic products"
        )

    def test_category_created(self):
        self.assertEqual(self.category.name, "Electronics")

    def test_category_slug_auto_generated(self):
        self.assertEqual(self.category.slug, "electronics")

    def test_category_str(self):
        self.assertEqual(str(self.category), "Electronics")


class ProductModelTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Electronics")
        self.product = Product.objects.create(
            name="Samsung Galaxy",
            description="A smartphone",
            price=500.00,
            stock=10,
            category=self.category
        )

    def test_product_created(self):
        self.assertEqual(self.product.name, "Samsung Galaxy")

    def test_product_slug_auto_generated(self):
        self.assertEqual(self.product.slug, "samsung-galaxy")

    def test_product_str(self):
        self.assertEqual(str(self.product), "Samsung Galaxy")


class ProductAPITest(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Electronics")
        self.product = Product.objects.create(
            name="Samsung Galaxy",
            description="A smartphone",
            price=500.00,
            stock=10,
            category=self.category
        )
        # Create vendor user
        self.vendor = User.objects.create_user(
            username="vendor1",
            email="vendor@test.com",
            password="TestPass123!",
            is_vendor=True
        )
        # Create normal user
        self.user = User.objects.create_user(
            username="user1",
            email="user@test.com",
            password="TestPass123!"
        )

    def test_anyone_can_list_products(self):
        response = self.client.get('/api/products/products/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_anyone_can_retrieve_product(self):
        response = self.client.get(f'/api/products/products/{self.product.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_cannot_create_product(self):
        data = {
            'name': 'iPhone',
            'description': 'Apple phone',
            'price': 999.00,
            'stock': 5,
            'category': self.category.id
        }
        response = self.client.post('/api/products/products/', data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_normal_user_cannot_create_product(self):
        self.client.force_authenticate(user=self.user)
        data = {
            'name': 'iPhone',
            'description': 'Apple phone',
            'price': 999.00,
            'stock': 5,
            'category': self.category.id
        }
        response = self.client.post('/api/products/products/', data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_vendor_can_create_product(self):
        self.client.force_authenticate(user=self.vendor)
        data = {
            'name': 'iPhone',
            'description': 'Apple phone',
            'price': 999.00,
            'stock': 5,
            'category': self.category.id
        }
        response = self.client.post('/api/products/products/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_product_price_cannot_be_negative(self):
        self.client.force_authenticate(user=self.vendor)
        data = {
            'name': 'iPhone',
            'description': 'Apple phone',
            'price': -100,
            'stock': 5,
            'category': self.category.id
        }
        response = self.client.post('/api/products/products/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

