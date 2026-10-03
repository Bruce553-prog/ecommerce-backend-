"""
Authorization tests for the products app (products, categories, reviews).

Run with:
    python3 manage.py test products.test_authorization -v 2

Roles used:
    customer / other_customer : ordinary shoppers
    vendor_a / vendor_b       : two different sellers
    admin                     : staff account

A response of 403 or 404 both count as "denied". A 200/201 where it shouldn't be,
or a 500 crash, means a real problem.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .models import Category, Product, Review

User = get_user_model()
PASSWORD = 'Str0ng!Passw0rd#2026'

PRODUCTS = '/api/products/products/'
CATEGORIES = '/api/products/categories/'


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


class ProductAuthorizationTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.customer = make_user('customer')
        cls.other_customer = make_user('othercustomer')
        cls.vendor_a = make_user('vendora', is_vendor=True)
        cls.vendor_b = make_user('vendorb', is_vendor=True)
        cls.admin = make_user('admin', is_staff=True, is_superuser=True)

        cls.category = Category.objects.create(name='Test Category')

        cls.product_a = Product.objects.create(
            name='Vendor A Product', description='Made by A', price=Decimal('100.00'),
            stock=10, category=cls.category, created_by=cls.vendor_a,
        )
        cls.product_b = Product.objects.create(
            name='Vendor B Product', description='Made by B', price=Decimal('200.00'),
            stock=10, category=cls.category, created_by=cls.vendor_b,
        )
        cls.legacy_product = Product.objects.create(
            name='Old Product', description='No owner', price=Decimal('300.00'),
            stock=10, category=cls.category,
        )

    def assertDenied(self, response):
        self.assertIn(
            response.status_code, (403, 404),
            f'Expected 403/404 but got {response.status_code}: {getattr(response, "data", "")}',
        )

    def new_product_payload(self, **overrides):
        data = {
            'name': 'Brand New Thing',
            'description': 'A test product',
            'price': '50.00',
            'stock': 5,
            'category': self.category.id,
        }
        data.update(overrides)
        return data

    # ---------- Reading ----------

    def test_anyone_can_browse_products(self):
        r = self.client.get(PRODUCTS)
        self.assertEqual(r.status_code, 200)
        r = self.client.get(f'{PRODUCTS}{self.product_a.id}/')
        self.assertEqual(r.status_code, 200)

    def test_anyone_can_read_categories(self):
        r = self.client.get(CATEGORIES)
        self.assertEqual(r.status_code, 200)

    def test_hidden_product_is_not_visible(self):
        hidden = Product.objects.create(
            name='Hidden', description='x', price=Decimal('10.00'), stock=1, is_active=False,
        )
        r = self.client.get(f'{PRODUCTS}{hidden.id}/')
        self.assertEqual(r.status_code, 404)

    # ---------- Customers and anonymous users cannot write ----------

    def test_anonymous_cannot_create_product(self):
        r = self.client.post(PRODUCTS, self.new_product_payload(), format='json')
        self.assertEqual(r.status_code, 401)

    def test_customer_cannot_create_product(self):
        self.client.force_authenticate(user=self.customer)
        r = self.client.post(PRODUCTS, self.new_product_payload(), format='json')
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Product.objects.filter(name='Brand New Thing').exists())

    def test_customer_cannot_edit_a_product(self):
        self.client.force_authenticate(user=self.customer)
        r = self.client.patch(f'{PRODUCTS}{self.product_a.id}/', {'price': '1.00'}, format='json')
        self.assertDenied(r)
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.price, Decimal('100.00'))

    def test_customer_cannot_delete_a_product(self):
        self.client.force_authenticate(user=self.customer)
        r = self.client.delete(f'{PRODUCTS}{self.product_a.id}/')
        self.assertDenied(r)
        self.product_a.refresh_from_db()
        self.assertTrue(self.product_a.is_active)

    def test_customer_cannot_create_edit_or_delete_categories(self):
        self.client.force_authenticate(user=self.customer)
        r = self.client.post(CATEGORIES, {'name': 'Sneaky'}, format='json')
        self.assertEqual(r.status_code, 403)
        r = self.client.patch(f'{CATEGORIES}{self.category.id}/', {'name': 'Hacked'}, format='json')
        self.assertEqual(r.status_code, 403)
        r = self.client.delete(f'{CATEGORIES}{self.category.id}/')
        self.assertEqual(r.status_code, 403)
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, 'Test Category')

    def test_vendor_cannot_create_categories(self):
        self.client.force_authenticate(user=self.vendor_a)
        r = self.client.post(CATEGORIES, {'name': 'Vendor Category'}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_admin_can_create_categories(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.post(CATEGORIES, {'name': 'Admin Category'}, format='json')
        self.assertEqual(r.status_code, 201, getattr(r, 'data', ''))

    # ---------- Vendors: own products only ----------

    def test_vendor_can_create_a_product_and_owns_it(self):
        self.client.force_authenticate(user=self.vendor_a)
        r = self.client.post(PRODUCTS, self.new_product_payload(), format='json')
        self.assertEqual(r.status_code, 201, getattr(r, 'data', ''))
        product = Product.objects.get(pk=r.data['id'])
        self.assertEqual(product.created_by_id, self.vendor_a.id)

    def test_vendor_cannot_assign_a_product_to_someone_else(self):
        self.client.force_authenticate(user=self.vendor_a)
        r = self.client.post(
            PRODUCTS,
            self.new_product_payload(created_by=self.vendor_b.id),
            format='json',
        )
        self.assertEqual(r.status_code, 201, getattr(r, 'data', ''))
        product = Product.objects.get(pk=r.data['id'])
        self.assertEqual(product.created_by_id, self.vendor_a.id)

    def test_vendor_can_edit_own_product(self):
        self.client.force_authenticate(user=self.vendor_a)
        r = self.client.patch(f'{PRODUCTS}{self.product_a.id}/', {'price': '120.00'}, format='json')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', ''))
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.price, Decimal('120.00'))

    def test_vendor_cannot_edit_another_vendors_product(self):
        self.client.force_authenticate(user=self.vendor_a)
        r = self.client.patch(f'{PRODUCTS}{self.product_b.id}/', {'price': '1.00'}, format='json')
        self.assertDenied(r)
        self.product_b.refresh_from_db()
        self.assertEqual(self.product_b.price, Decimal('200.00'))

    def test_vendor_cannot_delete_another_vendors_product(self):
        self.client.force_authenticate(user=self.vendor_a)
        r = self.client.delete(f'{PRODUCTS}{self.product_b.id}/')
        self.assertDenied(r)
        self.product_b.refresh_from_db()
        self.assertTrue(self.product_b.is_active)

    def test_vendor_cannot_edit_a_product_with_no_owner(self):
        self.client.force_authenticate(user=self.vendor_a)
        r = self.client.patch(f'{PRODUCTS}{self.legacy_product.id}/', {'price': '1.00'}, format='json')
        self.assertDenied(r)
        self.legacy_product.refresh_from_db()
        self.assertEqual(self.legacy_product.price, Decimal('300.00'))

    def test_deleting_a_product_hides_it_instead_of_erasing_it(self):
        self.client.force_authenticate(user=self.vendor_a)
        r = self.client.delete(f'{PRODUCTS}{self.product_a.id}/')
        self.assertEqual(r.status_code, 204)
        self.assertTrue(Product.objects.filter(pk=self.product_a.pk).exists())
        self.product_a.refresh_from_db()
        self.assertFalse(self.product_a.is_active)

    def test_admin_can_edit_any_product(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.patch(f'{PRODUCTS}{self.product_b.id}/', {'price': '250.00'}, format='json')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', ''))
        self.product_b.refresh_from_db()
        self.assertEqual(self.product_b.price, Decimal('250.00'))

    # ---------- Bad values ----------

    def test_negative_price_is_rejected(self):
        self.client.force_authenticate(user=self.vendor_a)
        r = self.client.post(PRODUCTS, self.new_product_payload(price='-50.00'), format='json')
        self.assertEqual(r.status_code, 400)

    def test_zero_price_is_rejected(self):
        self.client.force_authenticate(user=self.vendor_a)
        r = self.client.post(PRODUCTS, self.new_product_payload(price='0'), format='json')
        self.assertEqual(r.status_code, 400)

    def test_negative_price_on_edit_is_rejected(self):
        self.client.force_authenticate(user=self.vendor_a)
        r = self.client.patch(f'{PRODUCTS}{self.product_a.id}/', {'price': '-1.00'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.price, Decimal('100.00'))

    def test_negative_stock_is_rejected(self):
        self.client.force_authenticate(user=self.vendor_a)
        r = self.client.post(PRODUCTS, self.new_product_payload(stock=-5), format='json')
        self.assertEqual(r.status_code, 400)

    # ---------- Reviews ----------

    def review_url(self, product, action='add_review'):
        return f'{PRODUCTS}{product.id}/{action}/'

    def test_anonymous_cannot_add_a_review(self):
        r = self.client.post(self.review_url(self.product_a), {'rating': 5, 'comment': 'x'}, format='json')
        self.assertEqual(r.status_code, 401)

    def test_customer_can_add_a_review(self):
        self.client.force_authenticate(user=self.customer)
        r = self.client.post(self.review_url(self.product_a), {'rating': 5, 'comment': 'Great'}, format='json')
        self.assertEqual(r.status_code, 201, getattr(r, 'data', ''))
        review = Review.objects.get(product=self.product_a, customer=self.customer)
        self.assertEqual(review.rating, 5)

    def test_customer_cannot_review_the_same_product_twice(self):
        self.client.force_authenticate(user=self.customer)
        self.client.post(self.review_url(self.product_a), {'rating': 5}, format='json')
        r = self.client.post(self.review_url(self.product_a), {'rating': 1}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Review.objects.filter(product=self.product_a, customer=self.customer).count(), 1)

    def test_vendor_cannot_review_their_own_product(self):
        self.client.force_authenticate(user=self.vendor_a)
        r = self.client.post(self.review_url(self.product_a), {'rating': 5}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Review.objects.filter(product=self.product_a, customer=self.vendor_a).exists())

    def test_rating_outside_1_to_5_is_rejected(self):
        self.client.force_authenticate(user=self.customer)
        for bad in (0, 6, -1):
            r = self.client.post(self.review_url(self.product_a), {'rating': bad}, format='json')
            self.assertEqual(r.status_code, 400, f'rating {bad} was accepted')

    def test_very_long_review_comment_is_rejected(self):
        self.client.force_authenticate(user=self.customer)
        r = self.client.post(
            self.review_url(self.product_a),
            {'rating': 4, 'comment': 'x' * 2001}, format='json',
        )
        self.assertEqual(r.status_code, 400)

    def test_customer_can_delete_their_own_review(self):
        Review.objects.create(product=self.product_a, customer=self.customer, rating=4)
        self.client.force_authenticate(user=self.customer)
        r = self.client.delete(self.review_url(self.product_a, 'delete_review'))
        self.assertEqual(r.status_code, 200, getattr(r, 'data', ''))
        self.assertFalse(Review.objects.filter(product=self.product_a, customer=self.customer).exists())

    def test_customer_cannot_delete_someone_elses_review(self):
        Review.objects.create(product=self.product_a, customer=self.customer, rating=4)
        self.client.force_authenticate(user=self.other_customer)
        r = self.client.delete(self.review_url(self.product_a, 'delete_review'))
        self.assertEqual(r.status_code, 404)
        self.assertTrue(Review.objects.filter(product=self.product_a, customer=self.customer).exists())

    def test_reviews_do_not_expose_reviewer_emails(self):
        Review.objects.create(product=self.product_a, customer=self.customer, rating=4, comment='ok')
        r = self.client.get(self.review_url(self.product_a, 'reviews'))
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(self.customer.email, str(r.data))
        r = self.client.get(f'{PRODUCTS}{self.product_a.id}/')
        self.assertNotIn(self.customer.email, str(r.data))