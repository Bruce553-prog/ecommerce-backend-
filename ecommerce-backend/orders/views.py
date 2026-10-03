from django.db import transaction
from django.db.models import F
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


def parse_int(value):
    """Return value as an int, or None if it isn't a valid whole number."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class ShippingAddressViewSet(viewsets.ModelViewSet):
    serializer_class = ShippingAddressSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return ShippingAddress.objects.filter(customer=self.request.user).order_by('-is_default', '-id')

    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set a specific address as default."""
        address = self.get_object()
        with transaction.atomic():
            ShippingAddress.objects.filter(customer=request.user).update(is_default=False)
            address.is_default = True
            address.save()
        return Response({"detail": "Default address updated."})


class PickupStationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PickupStation.objects.filter(is_active=True).order_by('city', 'name')
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

        if quantity < 1:
            return Response({"error": "Quantity must be at least 1."}, status=status.HTTP_400_BAD_REQUEST)

        # Don't let the cart hold more than is in stock.
        existing = CartItem.objects.filter(cart=cart, product=product).first()
        new_total = quantity + (existing.quantity if existing else 0)
        if new_total > product.stock:
            return Response(
                {"error": f"Only {product.stock} in stock."},
                status=status.HTTP_400_BAD_REQUEST
            )

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
        product_id = parse_int(request.data.get('product_id'))

        if product_id is None:
            return Response({"error": "A valid product_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        CartItem.objects.filter(cart=cart, product_id=product_id).delete()
        return Response(CartSerializer(cart, context={'request': request}).data)

    @action(detail=False, methods=['post'])
    def update_quantity(self, request):
        """Set a specific quantity for a cart item."""
        cart = self.get_or_create_cart(request.user)
        product_id = parse_int(request.data.get('product_id'))
        quantity = parse_int(request.data.get('quantity'))

        if product_id is None or quantity is None:
            return Response(
                {"error": "A valid product_id and quantity are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if quantity <= 0:
            CartItem.objects.filter(cart=cart, product_id=product_id).delete()
            return Response({"detail": "Item removed from cart."})

        item = CartItem.objects.filter(cart=cart, product_id=product_id).select_related('product').first()
        if not item:
            return Response({"error": "Item not in cart."}, status=status.HTTP_404_NOT_FOUND)

        if quantity > item.product.stock:
            return Response(
                {"error": f"Only {item.product.stock} in stock."},
                status=status.HTTP_400_BAD_REQUEST
            )

        item.quantity = quantity
        item.save(update_fields=['quantity'])
        return Response(CartSerializer(cart, context={'request': request}).data)

    @action(detail=False, methods=['post'])
    def clear(self, request):
        """Empty the entire cart."""
        cart = self.get_or_create_cart(request.user)
        cart.items.all().delete()
        return Response({"detail": "Cart cleared."})


class OrderViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    # Must exist on the class so individual actions can set their own throttle_scope.
    throttle_scope = None

    def get_queryset(self):
        # Users only ever see their own orders.
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
        except (Order.DoesNotExist, ValueError):
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = OrderSerializer(order, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['post'], throttle_scope='checkout')
    def checkout(self, request):
        """Convert cart to order."""
        serializer = OrderCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        # All-or-nothing: if anything fails, stock and cart changes are rolled back.
        with transaction.atomic():
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
        with transaction.atomic():
            try:
                # Lock the row so two cancel requests can't both restore the stock.
                order = Order.objects.select_for_update().get(pk=pk, customer=request.user)
            except (Order.DoesNotExist, ValueError):
                return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

            if order.status != 'pending':
                return Response(
                    {"error": "Only pending orders can be cancelled."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Restore stock for each item
            for item in order.items.select_related('product').all():
                item.product.__class__.objects.filter(pk=item.product_id).update(
                    stock=F('stock') + item.quantity
                )

            order.status = 'cancelled'
            order.save()

        return Response({"detail": "Order cancelled successfully."})


class PaymentViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    # Must exist on the class so individual actions can set their own throttle_scope.
    throttle_scope = None
    serializer_class = PaymentSerializer

    def get_queryset(self):
        return Payment.objects.filter(order__customer=self.request.user)

    @action(detail=False, methods=['post'], throttle_scope='checkout')
    def initiate(self, request):
        """Initiate a payment for an order."""
        # SAFETY: this endpoint marks orders as paid WITHOUT taking any money.
        # It is only allowed while SIMULATE_PAYMENTS is on (defaults to DEBUG).
        # Replace it with the M-Pesa flow before going live.
        if not getattr(settings, 'SIMULATE_PAYMENTS', False):
            return Response(
                {"error": "Online payment is not available yet."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        order_id = request.data.get('order_id')
        # The frontend sends "payment_method"; older code sent "method". Accept both.
        method = request.data.get('method') or request.data.get('payment_method')

        if not order_id or not method:
            return Response({"error": "order_id and method are required."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            try:
                order = Order.objects.select_for_update().get(pk=order_id, customer=request.user)
            except (Order.DoesNotExist, ValueError, TypeError):
                return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

            # Cancelled or already-paid orders can't be paid.
            if order.status != 'pending':
                return Response({"error": "Only pending orders can be paid."}, status=status.HTTP_400_BAD_REQUEST)

            if Payment.objects.filter(order=order).exists():
                return Response({"error": "Payment already exists for this order."}, status=status.HTTP_400_BAD_REQUEST)

            # The amount always comes from the server, never from the browser.
            payment = Payment.objects.create(
                order=order,
                amount=order.get_total_price(),
                method=method,
                status='completed'  # simulated payment
            )

            # Update order status to confirmed after payment
            order.status = 'confirmed'
            order.save()

        # Send payment confirmation email
        send_mail(
            subject=f'Payment Confirmed - Order #{order.id} | The WCT',
            message=f'''Hi {request.user.username},

Your payment has been received and your order is now confirmed!

Order ID: #{order.id}
Amount Paid: KES {payment.amount}
Payment Method: {payment.method}
Status: Confirmed

Your order is now being processed and will be shipped soon.

Thank you for shopping with The WCT!

The WCT Team
''',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.user.email],
            fail_silently=True,
        )

        serializer = PaymentSerializer(payment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)