import os

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

User = get_user_model()

# Django hashes whatever it is given, so cap the length to stop huge-password abuse.
MAX_PASSWORD_LENGTH = 128

MAX_PROFILE_PICTURE_MB = 2
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


class UserSerializer(serializers.ModelSerializer):
    """For reading user profile data."""
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'phone',
            'profile_picture', 'is_vendor',
            'date_joined'
        ]
        read_only_fields = ['date_joined', 'is_vendor']


class RegisterSerializer(serializers.ModelSerializer):
    """For creating a new user account."""
    password = serializers.CharField(
        write_only=True,
        required=True,
        max_length=MAX_PASSWORD_LENGTH,
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        max_length=MAX_PASSWORD_LENGTH,
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password2', 'phone']

    def validate_email(self, value):
        # Store emails in lowercase and refuse duplicates regardless of case,
        # so one person can't hold two accounts and password reset stays unambiguous.
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Passwords do not match."})

        # Pass a user object so the "too similar to your username/email" rule actually works.
        candidate = User(
            username=attrs.get('username', ''),
            email=attrs.get('email', ''),
        )
        try:
            validate_password(attrs['password'], candidate)
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})

        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        # create_user() hashes the password.
        user = User.objects.create_user(**validated_data)
        return user


class ChangePasswordSerializer(serializers.Serializer):
    """For changing password while logged in."""
    old_password = serializers.CharField(
        write_only=True,
        required=True,
        max_length=MAX_PASSWORD_LENGTH,
    )
    new_password = serializers.CharField(
        write_only=True,
        required=True,
        max_length=MAX_PASSWORD_LENGTH,
    )

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def validate(self, attrs):
        user = self.context['request'].user

        if attrs['old_password'] == attrs['new_password']:
            raise serializers.ValidationError(
                {"new_password": "New password must be different from your current password."}
            )

        try:
            validate_password(attrs['new_password'], user)
        except DjangoValidationError as e:
            raise serializers.ValidationError({"new_password": list(e.messages)})

        return attrs

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class UpdateProfileSerializer(serializers.ModelSerializer):
    """For updating profile info, not password or email."""
    class Meta:
        model = User
        fields = ['username', 'phone', 'profile_picture']

    def validate_profile_picture(self, value):
        # Allow clearing the picture.
        if not value:
            return value

        if value.size > MAX_PROFILE_PICTURE_MB * 1024 * 1024:
            raise serializers.ValidationError(
                f"Image is too large. Maximum size is {MAX_PROFILE_PICTURE_MB} MB."
            )

        ext = os.path.splitext(value.name)[1].lower()
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            raise serializers.ValidationError("Only JPG, PNG or WEBP images are allowed.")

        return value