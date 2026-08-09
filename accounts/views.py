from django.contrib.auth import get_user_model
from django.conf import settings
from rest_framework import generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from drf_spectacular.utils import OpenApiResponse, extend_schema

from .emails import send_password_reset_email
from .models import Profile
from .serializers import (
    AdminLoginSerializer,
    ChangePasswordSerializer,
    EmployeeLoginSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    ProfileSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    UserSerializer,
    VendorLoginSerializer,
    VendorRegisterSerializer,
)
from .tokens import generate_token, verify_token

User = get_user_model()


@extend_schema(
    tags=["auth"],
    summary="Vendor / Store Owner Registration",
    description=(
        "Register as a new vendor. Creates your personal account and store in one step. "
        "Your store must be approved by a platform admin before you can log in."
    ),
    request=VendorRegisterSerializer,
    responses={
        201: OpenApiResponse(
            description=(
                "Registration submitted. Your store is pending approval."
            )
        ),
        400: OpenApiResponse(
            description="Validation error — duplicate username, email, store name, or slug."
        ),
    },
)
class VendorRegisterView(APIView):
    permission_classes = [AllowAny]
    serializer_class = VendorRegisterSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, tenant = serializer.save()

        return Response(
            {
                "message": (
                    "Registration submitted successfully. Your store is pending platform admin approval."
                ),
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "is_email_verified": user.is_email_verified,
                },
                "store": {
                    "name": tenant.name,
                    "slug": tenant.slug,
                    "status": "pending_approval",
                },
                "next_step": (
                    "A platform admin must approve your store before you can log in. "
                    "After approval, submit POST /api/auth/vendor/login/."
                ),
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=["auth"],
    summary="Customer Registration",
    description="Register a customer account.",
    request=RegisterSerializer,
    responses={
        201: OpenApiResponse(description="Registration successful."),
        400: OpenApiResponse(description="Validation error."),
    },
)
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                "message": "Registration successful.",
                "email": user.email,
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["auth"], request=LoginSerializer)
class LoginView(APIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


@extend_schema(tags=["auth"], request=AdminLoginSerializer)
class AdminLoginView(APIView):
    permission_classes = [AllowAny]
    serializer_class = AdminLoginSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["auth"],
    summary="Vendor / Store Owner Login",
    description=(
        "Login for store owners. The account email must be verified and the store "
        "must be active. The response includes the store slug for X-Tenant-Slug."
    ),
    request=VendorLoginSerializer,
    responses={
        200: OpenApiResponse(description="Login successful. Returns tokens and store information."),
        400: OpenApiResponse(
            description="Invalid credentials, unverified email, inactive store, or not a store owner."
        ),
    },
)
class VendorLoginView(APIView):
    permission_classes = [AllowAny]
    serializer_class = VendorLoginSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["auth"],
    summary="Employee Login",
    description=(
        "Login for store employees such as managers, staff, or viewers. "
        "The user must be an active member of the requested store."
    ),
    request=EmployeeLoginSerializer,
    responses={
        200: OpenApiResponse(description="Login successful. Returns tokens, store, and role."),
        400: OpenApiResponse(
            description="Invalid credentials, unverified email, inactive store, or invalid membership."
        ),
    },
)
class EmployeeLoginView(APIView):
    permission_classes = [AllowAny]
    serializer_class = EmployeeLoginSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["auth"],
    responses={200: UserSerializer},
    description="Get the currently authenticated user's information.",
)
class MeView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get(self, request):
        serializer = self.serializer_class(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    @extend_schema(
        summary="Change Password",
        description="Change the password for the currently logged-in user.",
        request=ChangePasswordSerializer,
        responses={
            200: OpenApiResponse(description="Password changed successfully."),
            400: OpenApiResponse(description="Validation error."),
        },
        tags=["auth"],
    )
    def post(self, request):
        serializer = self.serializer_class(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"message": "Password changed successfully. Please log in again."},
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer

    @extend_schema(
        summary="Logout",
        description="Blacklist the refresh token to log out the current user.",
        request=LogoutSerializer,
        responses={
            200: OpenApiResponse(description="Logged out successfully."),
            400: OpenApiResponse(description="Invalid or expired token."),
        },
        tags=["auth"],
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            token = RefreshToken(serializer.validated_data["refresh"])
            token.blacklist()
        except TokenError:
            return Response(
                {"error": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"message": "Logged out successfully."},
            status=status.HTTP_200_OK,
        )


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    serializer_class = ProfileSerializer

    @extend_schema(
        summary="Get Profile",
        description="Get the profile of the currently logged-in user.",
        responses={200: ProfileSerializer},
        tags=["auth"],
    )
    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        serializer = self.serializer_class(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Update Profile",
        description="Update profile details and avatar.",
        request=ProfileSerializer,
        responses={200: ProfileSerializer},
        tags=["auth"],
    )
    def patch(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        serializer = self.serializer_class(
            profile,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    serializer_class = ForgotPasswordSerializer

    @extend_schema(
        summary="Forgot Password",
        description="Send a password reset link to the configured email for the requested account.",
        request=ForgotPasswordSerializer,
        responses={
            200: OpenApiResponse(description="Password reset email sent if the account exists."),
        },
        tags=["auth"],
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        try:
            user = User.objects.get(email__iexact=email)
            token = generate_token(user.id, "reset_password")
            send_password_reset_email(user, token)
        except User.DoesNotExist:
            pass

        return Response(
            {
                "message": (
                    "If an account with this email exists, a password reset link has been sent."
                ),
                "email": email,
            },
            status=status.HTTP_200_OK,
        )


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    serializer_class = ResetPasswordSerializer

    @extend_schema(
        summary="Reset Password",
        description="Reset a user's password using a valid reset token.",
        request=ResetPasswordSerializer,
        responses={
            200: OpenApiResponse(description="Password reset successfully."),
            400: OpenApiResponse(description="Invalid or expired password reset token."),
        },
        tags=["auth"],
    )
    def post(self, request, token=None):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = verify_token(
            token,
            "reset_password",
            max_age_seconds=settings.PASSWORD_RESET_TOKEN_EXPIRY_DAYS * 86400,
        )

        if not user_id:
            return Response(
                {
                    "message": "Password reset token is invalid or has expired."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {
                    "message": "Password reset token is invalid or has expired."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data["password"])
        user.save(update_fields=["password"])

        return Response(
            {"message": "Password has been reset successfully. You can now log in."},
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["auth"],
    summary="Verify Email",
    description="Verify a newly registered user's email using the token sent by email.",
    responses={
        200: OpenApiResponse(description="Email verified successfully."),
        400: OpenApiResponse(description="Invalid or expired verification token."),
        404: OpenApiResponse(description="User not found."),
    },
)
class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token):
        user_id = verify_token(token, "email_verification")

        if not user_id:
            return Response(
                {"message": "Verification link is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"message": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.is_email_verified:
            return Response(
                {"message": "Email is already verified."},
                status=status.HTTP_200_OK,
            )

        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])

        return Response(
            {"message": "Email verified successfully. You can now log in."},
            status=status.HTTP_200_OK,
        )