from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOwner(BasePermission):
    """Allow access only to the owner of the object."""
    def has_object_permission(self, request, view, obj):
        return obj.customer == request.user


class IsVendor(BasePermission):
    """Allow access only to vendors."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_vendor


class IsVendorOrReadOnly(BasePermission):
    """Vendors can do anything, others can only read."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_authenticated and request.user.is_vendor


class IsOwnerOrAdmin(BasePermission):
    """Allow access to the owner or an admin."""
    def has_object_permission(self, request, view, obj):
        return request.user.is_staff or obj.customer == request.user


class IsAdminOrReadOnly(BasePermission):
    """Admins can do anything, others can only read."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_authenticated and request.user.is_staff