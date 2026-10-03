from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CartViewSet, OrderViewSet, ShippingAddressViewSet, PaymentViewSet, PickupStationViewSet

router = DefaultRouter()
router.register(r'cart', CartViewSet, basename='cart')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'shipping-addresses', ShippingAddressViewSet, basename='shipping-address')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'pickup-stations', PickupStationViewSet, basename='pickup-station')

urlpatterns = [
    path('', include(router.urls)),
]