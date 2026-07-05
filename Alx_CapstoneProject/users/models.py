from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    email = models.EmailField(unique=True, blank=False)
    phone = models.CharField(max_length=20, blank=True, null=True)
    profile_picture = models.ImageField(
        upload_to="users/profiles/",
        blank=True,
        null=True
    )
    is_vendor = models.BooleanField(default=False)

    # Use email as the primary login identifier
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']  # still required for createsuperuser

    def __str__(self):
        return self.email