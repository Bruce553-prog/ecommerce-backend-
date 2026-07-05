from rest_framework import serializers
from .models import Cart, CartItem, Order, OrderItem, ShippingAddress, Payment
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
        # Auto-assign the logged-in user
        user = self.context['request'].user
        return ShippingAddress.objects.create(customer=user, **validated_data)


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
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'customer', 'shipping_address',
            'status', 'items', 'total_price',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['customer', 'status', 'created_at', 'updated_at']

    def get_total_price(self, obj):
        return obj.get_total_price()
class OrderCreateSerializer(serializers.Serializer):
    """Converts the user's cart into an order."""
    shipping_address_id = serializers.PrimaryKeyRelatedField(
        queryset=ShippingAddress.objects.all()
    )

    def create(self, validated_data):
        user = self.context['request'].user
        shipping_address = validated_data['shipping_address_id']
        cart = Cart.objects.get(customer=user)
        cart_items = cart.items.select_related('product').all()

        if not cart_items.exists():
            raise serializers.ValidationError("Your cart is empty.")

        # Check stock availability before creating the order
        for item in cart_items:
            if item.quantity > item.product.stock:
                raise serializers.ValidationError(
                    f"Not enough stock for '{item.product.name}'. "
                    f"Available: {item.product.stock}, Requested: {item.quantity}."
                )

        # Create the order
        order = Order.objects.create(
            customer=user,
            shipping_address=shipping_address
        )

        # Move cart items to order items and reduce stock
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price_at_purchase=item.product.price
            )
            # Reduce stock
            item.product.stock -= item.quantity
            item.product.save()

        # Clear the cart
        cart_items.delete()

        return order



class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'id', 'order', 'amount', 'method',
            'status', 'transaction_id', 'paid_at', 'created_at'
        ]
        read_only_fields = ['status', 'paid_at', 'created_at']