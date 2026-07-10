

A fully functional **Django-based e-commerce platform** that allows users to **sign up, log in, browse products, add to cart, and place orders**.  
The system includes a **RESTful API** with JWT authentication, **role-based access control** for vendors and administrators, and **automated stock management**.

---

## 🚀 Features

### 👥 User Management
- Custom **User model** with roles (`admin`, `vendor`, `customer`).
- Secure **signup**, **login**, and **logout** system with **JWT tokens**.
- User **profiles** with editable details and profile pictures.
- **Admin dashboard** for managing users.
- Vendors can be granted or revoked by admins.

### 🛒 Product Management
- Vendors and admins can **add, update, and delete** products.
- Products grouped into **categories** with auto-generated slugs.
- Support for **multiple product images**.
- Customers can **browse, search, and filter** products.
- API endpoints secured with **authentication**.

### 🛒 Cart Management
- Every user gets an **automatic cart** on registration.
- Add, remove, update quantity, and clear cart items.
- Cart calculates **subtotals and totals** automatically.

### 📦 Order Management
- Customers can **checkout from cart** to create orders.
- Each order contains multiple **order items** with price snapshots.
- Order status tracking (`Pending`, `Paid`, `Shipped`, `Delivered`, `Cancelled`).
- **Stock automatically reduces** when an order is placed.
- **Stock restored** when an order is cancelled.
- Only **authenticated users** can access their orders.

### 📍 Shipping Addresses
- Users can manage **multiple shipping addresses**.
- Set a **default address** for quick checkout.

### 💳 Payment
- Initiate payments for orders.
- Payment status tracking (`Pending`, `Completed`, `Failed`, `Refunded`).
- Ready for integration with **M-Pesa, Stripe, or PayPal**.

### 🔐 Authentication & Permissions
- **JWT token-based authentication** (access + refresh tokens).
- Token **blacklisting** on logout.
- Non-authenticated users are **restricted** from protected routes.
- **Role-based access control** for admins and vendors.
- Users can only access their **own data**.

---

## 🧰 Technologies Used

| Category | Tool |
|----------|------|
| Framework | Django 4.2 |
| REST API | Django REST Framework |
| Authentication | JWT (djangorestframework-simplejwt) |
| Database | PostgreSQL |
| Static Files | Whitenoise |
| filtering | django-filter |
| Environment | python-decouple |
| Image Handling | Pillow |
| Version Control | Git & GitHub |

---

## ⚙️ Setup & Installation

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd Alx_CapstoneProject
```

### 2. Install dependencies
```bash
pip3 install -r requirements.txt
```

### 3. Create .env file
```env
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_NAME=ecommerce_db
DB_USER=ecommerce_user
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=5432
```

### 4. Run migrations
```bash
python3 manage.py migrate
```

### 5. Create superuser
```bash
python3 manage.py createsuperuser
```

### 6. Run server
```bash
python3 manage.py runserver
```

---

## 🔗 API Endpoints

### 🔐 Authentication
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/users/register/` | Register new user | No |
| POST | `/api/users/login/` | Login and get tokens | No |
| POST | `/api/users/token/refresh/` | Refresh access token | No |
| POST | `/api/users/logout/` | Logout and blacklist token | Yes |

### 👤 Users
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/users/users/me/` | Get current user profile | Yes |
| PUT/PATCH | `/api/users/users/update_profile/` | Update profile | Yes |
| POST | `/api/users/users/change_password/` | Change password | Yes |
| DELETE | `/api/users/users/delete_account/` | Delete account | Yes |

### 🛍️ Products
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/products/products/` | List all products | No |
| GET | `/api/products/products/{id}/` | Get product detail | No |
| POST | `/api/products/products/` | Create product | Vendor |
| PUT/PATCH | `/api/products/products/{id}/` | Update product | Vendor |
| DELETE | `/api/products/products/{id}/` | Delete product | Vendor |
| GET | `/api/products/products/by_category/?slug=x` | Filter by category | No |
| GET | `/api/products/categories/` | List categories | No |
| POST | `/api/products/categories/` | Create category | Admin |

### 🛒 Cart
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/orders/cart/my_cart/` | View cart | Yes |
| POST | `/api/orders/cart/add_item/` | Add item to cart | Yes |
| POST | `/api/orders/cart/remove_item/` | Remove item | Yes |
| POST | `/api/orders/cart/update_quantity/` | Update quantity | Yes |
| POST | `/api/orders/cart/clear/` | Clear cart | Yes |

### 📦 Orders
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/orders/orders/my_orders/` | List my orders | Yes |
| GET | `/api/orders/orders/{id}/detail_order/` | Get order detail | Yes |
| POST | `/api/orders/orders/checkout/` | Place order from cart | Yes |
| POST | `/api/orders/orders/{id}/cancel/` | Cancel order | Yes |

### 📍 Shipping Addresses
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/orders/shipping-addresses/` | List my addresses | Yes |
| POST | `/api/orders/shipping-addresses/` | Add new address | Yes |
| PUT/PATCH | `/api/orders/shipping-addresses/{id}/` | Update address | Yes |
| DELETE | `/api/orders/shipping-addresses/{id}/` | Delete address | Yes |
| POST | `/api/orders/shipping-addresses/{id}/set_default/` | Set default | Yes |

### 💳 Payments
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/orders/payments/initiate/` | Initiate payment | Yes |

---

## 🔍 Filtering & Search

| Query | Example | Description |
|-------|---------|-------------|
| `search` | `?search=samsung` | Search by name or description |
| `category` | `?category=electronics` | Filter by category slug |
| `min_price` | `?min_price=100` | Minimum price |
| `max_price` | `?max_price=500` | Maximum price |
| `in_stock` | `?in_stock=true` | Only in-stock products |
| `ordering` | `?ordering=price` | Order by price ascending |
| `ordering` | `?ordering=-price` | Order by price descending |

---

## 🧪 Running Tests

```bash
python3 manage.py test
```

---

## 👨‍💻 Author Information

| Field | Details |
|-------|---------|
| **Name** | Bruce Wyllis |
| **Role** | Django Backend Developer |
| **Project** | ALX_Capstone_Project |