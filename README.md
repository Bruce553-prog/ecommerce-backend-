# 🛍️ ALX Capstone Project

A fully functional **Django-based e-commerce and booking platform** that allows users to **sign up, log in, browse products, and make orders**.  
The system also includes a **RESTful API** for integrations and **admin management** for vendors and site administrators.

---

## 🚀 Features

### 👥 User Management
- Custom **User model** with roles (`admin`, `vendor`, `customer`).
- Secure **signup**, **login**, and **logout** system.
- User **profiles** with editable details.
- **Admin dashboard** for managing users.

### 🛒 Product Management
- Vendors and admins can **add, update, and delete** products.
- Products grouped into **categories**.
- Customers can **view available products**.
- API endpoints secured with **authentication**.

### 📦 Order Management
- Customers can **create and view orders**.
- Each order contains multiple **order items**.
- Order status tracking (`Pending`, `Processing`, `Completed`).
- Only **authenticated users** can access their orders.

### 🔐 Authentication & Permissions
- **Token-based authentication** (via Django REST Framework).
- Non-authenticated users are **restricted** from accessing protected routes.
- **Role-based access control** for admins and vendors.

---

## 🧰 Technologies Used

| Category | Tool |
|-----------|------|
| Framework | Django |
| REST API | Django REST Framework |
| Database | SQLite (default) |
| Frontend | HTML |
| Version Control | Git & GitHub |

---

## 👨‍💻 Author Information

| Field | Details |
|--------|----------|
| **Name** | Bruce Wyllis |
| **Role** | Django Backend Developer |
| **Project** | ALX_Capstone_Project |
