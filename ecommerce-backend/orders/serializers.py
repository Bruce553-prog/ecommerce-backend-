from django.db import transaction
from django.db.models import F
from rest_framework import serializers
from .models import (
    Cart, CartItem, Order, OrderItem, ShippingAddress, Payment, PickupStation,
    DELIVERY_FEES,
)
from products.models import Product
from products.serializers import ProductSerializer


class ShippingAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingAddress
        fields = [
            'id', 'full_name', 'phone',
            'address_line1', 'address_line2',
            'city', 'country', 'is_default'
        ]

    def create(self, validated_data):
        # The owner is always the logged-in user, whatever the client sends.
        validated_data['customer'] = self.context['request'].user
        return super().create(validated_data)


class PickupStationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PickupStation
        fields = ['id', 'name', 'location', 'city']


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'product_id', 'quantity', 'subtotal']

    def get_subtotal(self, obj):
        return obj.get_subtotal()

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be at least 1.")
        return value


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'items', 'total', 'created_at', 'updated_at']

    def get_total(self, obj):
        return obj.get_total()


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'price_at_purchase', 'subtotal']

    def get_subtotal(self, obj):
        return obj.get_subtotal()


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    shipping_address = ShippingAddressSerializer(read_only=True)
    pickup_station = PickupStationSerializer(read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'customer', 'shipping_address',
            'pickup_station', 'delivery_method',
            'delivery_fee', 'status', 'items', 'total_price',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['customer', 'delivery_fee', 'status', 'created_at', 'updated_at']

    def get_total_price(self, obj):
        return obj.get_total_price()


class OrderCreateSerializer(serializers.Serializer):
    """Converts the user's cart into an order."""
    shipping_address_id = serializers.PrimaryKeyRelatedField(
        queryset=ShippingAddress.objects.none(),  # narrowed to the user's own addresses in get_fields()
        required=False,
        allow_null=True
    )
    pickup_station_id = serializers.PrimaryKeyRelatedField(
        queryset=PickupStation.objects.filter(is_active=True),
        required=False,
        allow_null=True
    )
    delivery_method = serializers.ChoiceField(
        choices=['delivery', 'pickup'],
        default='delivery'
    )

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # A user can only choose one of their OWN addresses. Someone else's address
            # gets the same "does not exist" error as an address that isn't there.
            fields['shipping_address_id'].queryset = ShippingAddress.objects.filter(
                customer=request.user
            )
        return fields

    def validate(self, attrs):
        method = attrs.get('delivery_method', 'delivery')
        if method == 'delivery' and not attrs.get('shipping_address_id'):
            raise serializers.ValidationError("Shipping address is required for home delivery.")
        if method == 'pickup' and not attrs.get('pickup_station_id'):
            raise serializers.ValidationError("Pickup station is required for pickup orders.")
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        delivery_method = validated_data.get('delivery_method', 'delivery')

        # Keep only the destination that matches the delivery method.
        shipping_address = (
            validated_data.get('shipping_address_id') if delivery_method == 'delivery' else None
        )
        pickup_station = (
            validated_data.get('pickup_station_id') if delivery_method == 'pickup' else None
        )

        with transaction.atomic():
            # Lock the cart and the products so two checkouts at the same moment
            # can't both buy the last item.
            try:
                cart = Cart.objects.select_for_update().get(customer=user)
            except Cart.DoesNotExist:
                raise serializers.ValidationError("Your cart is empty.")

            cart_items = list(cart.items.all())
            if not cart_items:
                raise serializers.ValidationError("Your cart is empty.")

            products = {
                p.pk: p for p in Product.objects.select_for_update().filter(
                    pk__in=[i.product_id for i in cart_items]
                )
            }

            for item in cart_items:
                product = products.get(item.product_id)
                if product is None or not getattr(product, 'is_active', True):
                    raise serializers.ValidationError(
                        "A product in your cart is no longer available."
                    )
                if item.quantity > product.stock:
                    raise serializers.ValidationError(
                        f"Not enough stock for '{product.name}'. "
                        f"Available: {product.stock}, Requested: {item.quantity}."
                    )

            order = Order.objects.create(
                customer=user,
                shipping_address=shipping_address,
                pickup_station=pickup_station,
                delivery_method=delivery_method,
                # Fee is decided here on the server, never taken from the browser.
                delivery_fee=DELIVERY_FEES[delivery_method],
            )

            for item in cart_items:
                product = products[item.product_id]
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=item.quantity,
                    # Price always comes from the database, never from the browser.
                    price_at_purchase=product.price
                )
                # Subtract in the database so concurrent updates can't overwrite each other.
                Product.objects.filter(pk=product.pk).update(
                    stock=F('stock') - item.quantity
                )

            cart.items.all().delete()

        return order


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'id', 'order', 'amount', 'method',
            'status', 'transaction_id', 'paid_at', 'created_at'
        ]
        # Output only: payments are created by the server, never from client input.
        read_only_fields = fields