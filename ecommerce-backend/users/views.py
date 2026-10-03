import logging

from rest_framework import viewsets, permissions, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.token_blacklist.models import (
    OutstandingToken,
    BlacklistedToken,
)
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings

from .serializers import (
    UserSerializer,
    RegisterSerializer,
    ChangePasswordSerializer,
    UpdateProfileSerializer
)

User = get_user_model()
logger = logging.getLogger(__name__)


def revoke_all_tokens(user):
    """Blacklist every refresh token issued to this user (logs them out everywhere)."""
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


class RegisterView(generics.CreateAPIView):
    """Register a new user account."""
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'register'


class LoginView(TokenObtainPairView):
    """Login (issues access + refresh tokens), rate limited against brute force."""
    throttle_scope = 'login'


class LogoutView(APIView):
    """Blacklist the refresh token so it can never be used again."""
    permission_classes = [permissions.AllowAny]
    # No authentication here, so logout still works when the access token has already expired.
    authentication_classes = []

    def post(self, request):
        refresh = request.data.get('refresh')
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except TokenError:
                # Already expired, blacklisted or invalid: nothing more to revoke.
                pass
        return Response(status=status.HTTP_205_RESET_CONTENT)


class UserViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    # Must exist on the class so individual actions can set their own throttle_scope.
    throttle_scope = None
    # JSONParser added: without it, JSON requests from the React app get a 415 error.
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        # Users can only ever see themselves.
        return User.objects.filter(id=self.request.user.id)

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current logged in user profile."""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['put', 'patch'])
    def update_profile(self, request):
        """Update username, phone, or profile picture."""
        serializer = UpdateProfileSerializer(
            request.user,
            data=request.data,
            partial=request.method == 'PATCH'
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=['post'], throttle_scope='password_change')
    def change_password(self, request):
        """Change password while logged in. All old sessions are revoked."""
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Log out every other device/session, then hand back fresh tokens
        # so the current session can carry on.
        revoke_all_tokens(request.user)
        refresh = RefreshToken.for_user(request.user)
        return Response({
            "detail": "Password changed successfully.",
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        })

    @action(detail=False, methods=['delete'], throttle_scope='password_change')
    def delete_account(self, request):
        """Deactivate the current user's account. Requires the password."""
        user = request.user
        password = request.data.get('password')
        if not password or not user.check_password(password):
            return Response(
                {"error": "Incorrect password."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Deactivate instead of deleting so past orders and payment records are kept.
        revoke_all_tokens(user)
        user.is_active = False
        user.save(update_fields=['is_active'])
        return Response({"detail": "Account deleted successfully."})


class AdminUserViewSet(viewsets.ModelViewSet):
    """Admin-only viewset to manage all users."""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]

    @action(detail=True, methods=['post'])
    def toggle_vendor(self, request, pk=None):
        """Grant or revoke vendor status for a user."""
        user = self.get_object()
        user.is_vendor = not user.is_vendor
        user.save()
        status_str = "granted" if user.is_vendor else "revoked"
        return Response({"detail": f"Vendor status {status_str} for {user.email}."})


GENERIC_RESET_MESSAGE = (
    "If an account exists for that email, a password reset link has been sent."
)


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_scope = 'password_reset'

    def post(self, request):
        email = (request.data.get('email') or '').strip()
        if not email:
            return Response({"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email__iexact=email, is_active=True).first()

        if user:
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_link = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password/{uid}/{token}/"
            minutes = settings.PASSWORD_RESET_TIMEOUT // 60

            try:
                send_mail(
                    subject='Password Reset - The WCT',
                    message=f'''Hi {user.username},

You requested a password reset for your The WCT account.

Click the link below to reset your password:
{reset_link}

This link will expire in {minutes} minutes and can only be used once.

If you did not request this, please ignore this email.

The WCT Team
''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
            except Exception:
                # Log it, but answer exactly the same way so nobody can tell
                # whether the email exists.
                logger.exception("Password reset email failed for user id %s", user.pk)

        # Same response whether or not the email exists.
        return Response({"detail": GENERIC_RESET_MESSAGE})


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_scope = 'password_reset_confirm'

    def post(self, request):
        uid = request.data.get('uid')
        token = request.data.get('token')
        new_password = request.data.get('new_password')

        if not uid or not token or not new_password:
            return Response(
                {"error": "uid, token and new_password are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id, is_active=True)
        except Exception:
            return Response({"error": "Invalid reset link."}, status=status.HTTP_400_BAD_REQUEST)

        # Token is tied to the current password hash, so it stops working once used.
        if not default_token_generator.check_token(user, token):
            return Response(
                {"error": "Reset link is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Enforce the same password rules as registration.
        try:
            validate_password(new_password, user)
        except DjangoValidationError as e:
            return Response({"error": " ".join(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        # Anyone logged in with the old password gets logged out.
        revoke_all_tokens(user)

        return Response({"detail": "Password reset successfully. You can now login."})