from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOwner(BasePermission):
    """Allow access only to the owner of the object."""
    def has_object_permission(self, request, view, obj):
        # getattr: an object with no "customer" field is denied instead of crashing with a 500.
        return getattr(obj, 'customer', None) == request.user


class IsVendor(BasePermission):
    """Allow access only to vendors."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_vendor


class IsVendorOrReadOnly(BasePermission):
    """
    Everyone can read. Vendors (and staff) can create products.
    Changing or deleting a product is only allowed for the person who created it, or staff.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_authenticated and (
            request.user.is_vendor or request.user.is_staff
        )

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.user.is_staff:
            return True
        # Second safety net behind the view's own filtering: even if a vendor reached
        # someone else's product, this still refuses the change.
        owner_id = getattr(obj, 'created_by_id', None)
        return owner_id is not None and owner_id == request.user.id


class IsOwnerOrAdmin(BasePermission):
    """Allow access to the owner or an admin."""
    def has_object_permission(self, request, view, obj):
        return request.user.is_staff or getattr(obj, 'customer', None) == request.user


class IsAdminOrReadOnly(BasePermission):
    """Admins can do anything, others can only read."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_authenticated and request.user.is_staff