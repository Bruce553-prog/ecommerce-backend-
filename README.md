**ALx Capstone Project**
A fully functional Django-based e-commerce and booking platform that allows users to sign up, log in, browse products, and make orders.
The system also includes a RESTful API for integrations and admin management for vendors and site administrators.
**Features
User Management**
Custom User model with roles (admin, vendor, customer).
Secure signup, login, and logout system.
User profiles with editable details.
Admin dashboard for managing users.
**Product Management**
Vendors and admins can add, update, and delete products.
Products grouped into categories.
Customers can view available products.
API endpoints secured with authentication.
**Order Management**
Customers can create and view orders.
Each order contains multiple order items.
Order status tracking (Pending, Processing, Completed).
Only authenticated users can access their orders.
**Authentication & Permissions**
Token-based authentication (via DRF).
Non-authenticated users are restricted from making bookings or accessing protected routes.
Role-based access control for admins and vendors.
**Technologies used**
Framework; Django
REST API;Django Rest Framework
Database;The default SQLite
Frontend;HTML
Version control;Git and Github
**Installation guide**
after Installaation run python manage.py runserver to start development server  open your browser and visit the bellow urls
http://127.0.0.1:8000/admin/ — for admin panel
http://127.0.0.1:8000/api/products/ — for product APIs
http://127.0.0.1:8000/users/signup/ — for user registration

**API EndPoints**
Feature         Method          Endpoint             Description
Products        GET             api/products/        List all products
products        POST            /api/products/       for adding new product
Orders          GET             /api/orders/         List all user orders
Orders          POST            /api/orders/         Create a new order
Users           POST            /users/signup/       Register new account
Users           POST            /users/login/        log in existing users

**Admin Access**
Superusers can:
Manage Users, Products, and Orders.
View detailed customer activities.
Create new vendors or admins.

**Author**
Name: Bruce Wyllis
Role: Django Backend Developer
Project: ALX_Capstone_Project
