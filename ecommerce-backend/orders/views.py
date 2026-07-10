from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.mail import send_mail
from django.conf import settings
from users.permissions import IsOwner, IsOwnerOrAdmin
from .models import Cart, CartItem, Order, ShippingAddress, Payment, PickupStation
from .serializers import (
    CartSerializer,
    CartItemSerializer,
    OrderSerializer,
    OrderCreateSerializer,
    ShippingAddressSerializer,
    PaymentSerializer,
    PickupStationSerializer
)


class ShippingAddressViewSet(viewsets.ModelViewSet):
    serializer_class = ShippingAddressSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return ShippingAddress.objects.filter(customer=self.request.user)

    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set a specific address as default."""
        address = self.get_object()
        ShippingAddress.objects.filter(customer=request.user).update(is_default=False)
        address.is_default = True
        address.save()
        return Response({"detail": "Default address updated."})


class PickupStationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PickupStation.objects.filter(is_active=True)
    serializer_class = PickupStationSerializer
    permission_classes = [permissions.AllowAny]


class CartViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CartSerializer

    def get_or_create_cart(self, user):
        cart, _ = Cart.objects.get_or_create(customer=user)
        return cart

    @action(detail=False, methods=['get'])
    def my_cart(self, request):
        """Get the current user's cart."""
        cart = self.get_or_create_cart(request.user)
        serializer = CartSerializer(cart, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def add_item(self, request):
        """Add a product to the cart or increase quantity if already exists."""
        cart = self.get_or_create_cart(request.user)
        serializer = CartItemSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        product = serializer.validated_data['product']
        quantity = serializer.validated_data.get('quantity', 1)

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': quantity}
        )

        if not created:
            cart_item.quantity += quantity
            cart_item.save()

        return Response(CartSerializer(cart, context={'request': request}).data)

    @action(detail=False, methods=['post'])
    def remove_item(self, request):
        """Remove a product from the cart completely."""
        cart = self.get_or_create_cart(request.user)
        product_id = request.data.get('product_id')

        if not product_id:
            return Response({"error": "product_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        CartItem.objects.filter(cart=cart, product_id=product_id).delete()
        return Response(CartSerializer(cart, context={'request': request}).data)

    @action(detail=False, methods=['post'])
    def update_quantity(self, request):
        """Set a specific quantity for a cart item."""
        cart = self.get_or_create_cart(request.user)
        product_id = request.data.get('product_id')
        quantity = request.data.get('quantity')

        if not product_id or quantity is None:
            return Response({"error": "product_id and quantity are required."}, status=status.HTTP_400_BAD_REQUEST)

        if int(quantity) <= 0:
            CartItem.objects.filter(cart=cart, product_id=product_id).delete()
            return Response({"detail": "Item removed from cart."})

        CartItem.objects.filter(cart=cart, product_id=product_id).update(quantity=quantity)
        return Response(CartSerializer(cart, context={'request': request}).data)

    @action(detail=False, methods=['post'])
    def clear(self, request):
        """Empty the entire cart."""
        cart = self.get_or_create_cart(request.user)
        cart.items.all().delete()
        return Response({"detail": "Cart cleared."})


class OrderViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        return Order.objects.filter(
            customer=self.request.user
        ).select_related('shipping_address').prefetch_related('items__product')

    @action(detail=False, methods=['get'])
    def my_orders(self, request):
        """List all orders for the current user."""
        orders = self.get_queryset()
        serializer = OrderSerializer(orders, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def detail_order(self, request, pk=None):
        """Get a single order detail."""
        try:
            order = self.get_queryset().get(pk=pk)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = OrderSerializer(order, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def checkout(self, request):
        """Convert cart to order."""
        serializer = OrderCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()

        # Send order confirmation email
        items_list = '\n'.join([
            f"- {item.product.name} x {item.quantity} @ KES {item.price_at_purchase}"
            for item in order.items.all()
        ])

        send_mail(
            subject=f'Order Confirmation - Order #{order.id} | The WCT',
            message=f'''Hi {request.user.username},

Thank you for your order! Here are your order details:

Order ID: #{order.id}
Delivery Method: {order.delivery_method}

Items Ordered:
{items_list}

Total: KES {order.get_total_price()}

{"Shipping to: " + str(order.shipping_address) if order.shipping_address else "Pickup Station: " + str(order.pickup_station)}

Your order is currently being processed. We will notify you once it is shipped.

Thank you for shopping with The WCT!

The WCT Team
''',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.user.email],
            fail_silently=True,
        )

        return Response(
            OrderSerializer(order, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a pending order and restore stock."""
        try:
            order = self.get_queryset().get(pk=pk)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        if order.status != 'pending':
            return Response({"error": "Only pending orders can be cancelled."}, status=status.HTTP_400_BAD_REQUEST)

        # Restore stock for each item
        for item in order.items.select_related('product').all():
            item.product.stock += item.quantity
            item.product.save()

        order.status = 'cancelled'
        order.save()
        return Response({"detail": "Order cancelled successfully."})


class PaymentViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PaymentSerializer

    def get_queryset(self):
        return Payment.objects.filter(order__customer=self.request.user)

    @action(detail=False, methods=['post'])
    def initiate(self, request):
        """Initiate a payment for an order."""
        order_id = request.data.get('order_id')
        method = request.data.get('method')

        if not order_id or not method:
            return Response({"error": "order_id and method are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.get(pk=order_id, customer=request.user)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        if hasattr(order, 'payment'):
            return Response({"error": "Payment already exists for this order."}, status=status.HTTP_400_BAD_REQUEST)

        payment = Payment.objects.create(
            order=order,
            amount=order.get_total_price(),
            method=method
        )

        serializer = PaymentSerializer(payment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)