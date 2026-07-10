from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.core.mail import send_mail
from orders.models import Cart


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_cart(sender, instance, created, **kwargs):
    """Automatically create a cart when a new user registers."""
    if created:
        # Create cart
        Cart.objects.create(customer=instance)

        # Send welcome email
        send_mail(
            subject='Welcome to The WCT!',
            message=f'''Hi {instance.username},

Welcome to The WCT! Your account has been created successfully.

You can now:
- Browse our products
- Add items to your cart
- Place orders
- Choose home delivery or pickup station

Thank you for joining us!

The WCT Team
''',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[instance.email],
            fail_silently=True,
        )