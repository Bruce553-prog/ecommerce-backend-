from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from orders.models import Cart


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_cart(sender, instance, created, **kwargs):
    """Automatically create a cart when a new user registers."""
    if created:
        Cart.objects.create(customer=instance)