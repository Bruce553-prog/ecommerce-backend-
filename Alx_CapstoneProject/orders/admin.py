from django.contrib import admin
from .models import Cart, CartItem, Order, OrderItem, ShippingAddress, Payment, PickupStation


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'quantity', 'price_at_purchase']


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'status', 'total_price', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['customer__email', 'id']
    readonly_fields = ['created_at']
    inlines = [OrderItemInline]

    def total_price(self, obj):
        return f"${obj.get_total_price():.2f}"
    total_price.short_description = "Total Price"


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'product', 'quantity', 'price_at_purchase']
    search_fields = ['order__id', 'product__name']


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['customer', 'created_at']
    inlines = [CartItemInline]


@admin.register(ShippingAddress)
class ShippingAddressAdmin(admin.ModelAdmin):
    list_display = ['customer', 'full_name', 'city', 'country', 'is_default']
    search_fields = ['customer__email', 'full_name']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['order', 'amount', 'method','status', 'paid_at']
    list_filter = ['status', 'method']
@admin.register(PickupStation)
class PickupStationAdmin(admin.ModelAdmin):
    list_display = ['name', 'location', 'city', 'phone', 'is_active']
    list_filter = ['city', 'is_active']
    search_fields = ['name', 'city']