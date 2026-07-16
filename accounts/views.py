# accounts/views.py
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import models
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import Profile
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    AdminLoginSerializer,
    VendorRegisterSerializer,
    VendorLoginSerializer,
    EmployeeLoginSerializer,
    ChangePasswordSerializer,
    LogoutSerializer,
    ProfileSerializer,
    UserSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
    # Employee management serializers
    EmployeeCreateSerializer,
    EmployeeListSerializer,
    EmployeeUpdateSerializer,
    EmployeeBulkCreateSerializer,
    EmployeeActivityLogSerializer,
)
from .emails import send_password_reset_email, send_password_reset_confirmation

User = get_user_model()


# ============================================
# VENDOR REGISTRATION
# ============================================
@extend_schema(
    tags=['auth'],
    summary='Vendor / Store Owner Registration',
    description=(
        'Register as a new vendor. Creates your personal account and store in one step. '
        'Your store will be **inactive** until a platform admin approves it.'
    ),
    request=VendorRegisterSerializer,
    responses={
        201: OpenApiResponse(description='Registration submitted. Pending admin approval.'),
        400: OpenApiResponse(description='Validation error.'),
    },
)
class VendorRegisterView(APIView):
    permission_classes = [AllowAny]
    serializer_class = VendorRegisterSerializer

    def post(self, request):
        serializer = VendorRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, tenant = serializer.save()
        return Response(
            {
                'message': 'Registration submitted successfully. Your store is pending approval.',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                },
                'store': {
                    'name': tenant.name,
                    'slug': tenant.slug,
                    'status': 'pending_approval',
                },
            },
            status=status.HTTP_201_CREATED,
        )


# ============================================
# USER REGISTRATION
# ============================================
@extend_schema(
    tags=['auth'],
    summary='User Registration',
    description='Register a new user account.',
    request=RegisterSerializer,
    responses={
        201: OpenApiResponse(description='Registration successful.'),
        400: OpenApiResponse(description='Validation error.'),
    },
)
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Auto-verify email for now
        user.is_email_verified = True
        user.save()
        
        refresh = RefreshToken.for_user(user)
        
        return Response(
            {
                'message': 'Registration successful!',
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }
            },
            status=status.HTTP_201_CREATED
        )


# ============================================
# USER LOGIN
# ============================================
@extend_schema(
    tags=['auth'],
    summary='User Login',
    description='Login with username and password.',
    request=LoginSerializer,
    responses={
        200: OpenApiResponse(description='Login successful.'),
        400: OpenApiResponse(description='Validation error.'),
        401: OpenApiResponse(description='Invalid credentials.'),
    },
)
class LoginView(APIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


# ============================================
# ADMIN LOGIN
# ============================================
@extend_schema(
    tags=['auth'],
    summary='Admin Login',
    description='Login for admin users only.',
    request=AdminLoginSerializer,
    responses={
        200: OpenApiResponse(description='Admin login successful.'),
        400: OpenApiResponse(description='Validation error.'),
        401: OpenApiResponse(description='Invalid credentials or not admin.'),
    },
)
class AdminLoginView(APIView):
    permission_classes = [AllowAny]
    serializer_class = AdminLoginSerializer

    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


# ============================================
# VENDOR LOGIN
# ============================================
@extend_schema(
    tags=['auth'],
    summary='Vendor / Store Owner Login',
    description=(
        'Login for store owners (vendor admins). '
        'The response includes your store slug.'
    ),
    request=VendorLoginSerializer,
    responses={
        200: OpenApiResponse(description='Vendor login successful.'),
        400: OpenApiResponse(description='Validation error.'),
        401: OpenApiResponse(description='Invalid credentials or store not approved.'),
    },
)
class VendorLoginView(APIView):
    permission_classes = [AllowAny]
    serializer_class = VendorLoginSerializer

    def post(self, request):
        serializer = VendorLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


# ============================================
# EMPLOYEE LOGIN
# ============================================
@extend_schema(
    tags=['auth'],
    summary='Employee Login',
    description=(
        'Login for store employees (manager / staff / viewer). '
        'You must be added to the store by the owner first.'
    ),
    request=EmployeeLoginSerializer,
    responses={
        200: OpenApiResponse(description='Employee login successful.'),
        400: OpenApiResponse(description='Validation error.'),
        401: OpenApiResponse(description='Invalid credentials or not a member.'),
    },
)
class EmployeeLoginView(APIView):
    permission_classes = [AllowAny]
    serializer_class = EmployeeLoginSerializer

    def post(self, request):
        serializer = EmployeeLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


# ============================================
# GET CURRENT USER (ME)
# ============================================
@extend_schema(
    tags=['auth'],
    summary='Get Current User',
    description="Get current authenticated user's information.",
    responses={
        200: UserSerializer,
        401: OpenApiResponse(description='Authentication required.'),
    },
)
class MeView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ============================================
# CHANGE PASSWORD (Authenticated)
# ============================================
@extend_schema(
    tags=['auth'],
    summary='Change Password',
    description='Change password for the currently logged-in user.',
    request=ChangePasswordSerializer,
    responses={
        200: OpenApiResponse(description='Password changed successfully.'),
        400: OpenApiResponse(description='Validation error.'),
        401: OpenApiResponse(description='Authentication required.'),
    },
)
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {'message': 'Password changed successfully. Please log in again.'},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================
# LOGOUT
# ============================================
@extend_schema(
    tags=['auth'],
    summary='Logout',
    description='Blacklist the refresh token to log out the current user.',
    request=LogoutSerializer,
    responses={
        200: OpenApiResponse(description='Logged out successfully.'),
        400: OpenApiResponse(description='Invalid or expired token.'),
        401: OpenApiResponse(description='Authentication required.'),
    },
)
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        if serializer.is_valid():
            try:
                token = RefreshToken(serializer.validated_data['refresh'])
                token.blacklist()
                return Response(
                    {'message': 'Logged out successfully.'},
                    status=status.HTTP_200_OK
                )
            except TokenError:
                return Response(
                    {'error': 'Invalid or expired token.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================
# PROFILE (GET & UPDATE)
# ============================================
@extend_schema(
    tags=['auth'],
    summary='Profile Management',
    description='Get or update user profile.',
)
class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    serializer_class = ProfileSerializer

    @extend_schema(
        summary='Get Profile',
        description='Get the profile of the currently logged-in user.',
        responses={200: ProfileSerializer},
    )
    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        serializer = ProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary='Update Profile',
        description='Update profile details and avatar picture.',
        request=ProfileSerializer,
        responses={200: ProfileSerializer},
    )
    def patch(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        serializer = ProfileSerializer(
            profile,
            data=request.data,
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================
# FORGOT PASSWORD
# ============================================
@extend_schema(
    tags=['auth'],
    summary='Forgot Password',
    description='Send password reset link to user email.',
    request=ForgotPasswordSerializer,
    responses={
        200: OpenApiResponse(description='Reset link sent successfully.'),
        400: OpenApiResponse(description='Validation error.'),
        404: OpenApiResponse(description='Email not found.'),
    },
)
class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    serializer_class = ForgotPasswordSerializer

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'error': 'No user found with this email address.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Generate reset token
        token = user.generate_reset_token()
        
        # Send email (try, but don't fail if it doesn't work in development)
        email_sent = False
        try:
            send_password_reset_email(user, token)
            email_sent = True
        except Exception as e:
            print(f"Email error (ignored): {str(e)}")
        
        response_data = {
            'message': 'Password reset link has been sent to your email.' if email_sent else 'Password reset token generated.',
            'email': email,
            'email_sent': email_sent,
        }
        
        # Include token in development for testing
        if settings.DEBUG:
            response_data['token'] = token
            response_data['reset_url'] = f"{settings.FRONTEND_URL}/reset-password?token={token}"
            response_data['note'] = 'Copy this token and use it in /api/auth/reset-password/'
        
        return Response(response_data, status=status.HTTP_200_OK)


# ============================================
# RESET PASSWORD
# ============================================
@extend_schema(
    tags=['auth'],
    summary='Reset Password',
    description='Reset password using the token received via email.',
    request=ResetPasswordSerializer,
    responses={
        200: OpenApiResponse(description='Password reset successfully.'),
        400: OpenApiResponse(description='Invalid token or password validation error.'),
        404: OpenApiResponse(description='User not found.'),
    },
)
class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    serializer_class = ResetPasswordSerializer

    def post(self, request, token=None):
        # If token is in URL, use it; otherwise get from request body
        if token:
            data = request.data.copy()
            data['token'] = token
            serializer = ResetPasswordSerializer(data=data)
        else:
            serializer = ResetPasswordSerializer(data=request.data)
        
        serializer.is_valid(raise_exception=True)
        
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']
        
        try:
            user = User.objects.get(reset_password_token=token)
            
            if not user.is_reset_token_valid():
                return Response(
                    {
                        'error': 'Reset token has expired. Please request a new one.',
                        'expired': True
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Set new password
            user.set_password(new_password)
            user.reset_password_token = None
            user.reset_password_token_created_at = None
            user.save()
            
            # Send confirmation email (optional)
            try:
                send_password_reset_confirmation(user)
            except:
                pass
            
            return Response(
                {
                    'message': 'Password reset successful. You can now log in with your new password.',
                    'success': True
                },
                status=status.HTTP_200_OK
            )
            
        except User.DoesNotExist:
            return Response(
                {
                    'error': 'Invalid reset token.',
                    'success': False
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {
                    'error': 'An error occurred while resetting password.',
                    'detail': str(e) if settings.DEBUG else None,
                    'success': False
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ============================================
# VENDOR EMPLOYEE MANAGEMENT
# ============================================

@extend_schema(
    tags=['vendor'],
    summary='Vendor - Create Employee',
    description='Store owner can create a new employee account for their store.',
    request=EmployeeCreateSerializer,
    responses={
        201: OpenApiResponse(description='Employee created successfully.'),
        400: OpenApiResponse(description='Validation error.'),
        403: OpenApiResponse(description='Only store owner can perform this action.'),
    },
)
class VendorCreateEmployeeView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EmployeeCreateSerializer

    def post(self, request):
        from tenants.models import Tenant
        
        # Get tenant from header
        tenant_slug = request.headers.get('X-Tenant-Slug')
        if not tenant_slug:
            return Response(
                {'error': 'X-Tenant-Slug header is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            tenant = Tenant.objects.get(slug=tenant_slug, is_active=True)
        except Tenant.DoesNotExist:
            return Response(
                {'error': 'Store not found or inactive.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if user is the store owner
        if tenant.owner != request.user:
            return Response(
                {'error': 'Only the store owner can create employees.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Validate and create employee
        serializer = EmployeeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user, tenant_member = serializer.save(
            vendor_user=request.user,
            tenant=tenant
        )

        return Response(
            {
                'message': 'Employee created successfully.',
                'employee': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': tenant_member.role,
                },
                'store': {
                    'id': tenant.id,
                    'name': tenant.name,
                    'slug': tenant.slug,
                }
            },
            status=status.HTTP_201_CREATED
        )


@extend_schema(
    tags=['vendor'],
    summary='Vendor - List Employees',
    description='Store owner can list all employees in their store.',
    responses={
        200: OpenApiResponse(description='Employees retrieved successfully.'),
        403: OpenApiResponse(description='Only store owner can perform this action.'),
    },
)
class VendorListEmployeesView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EmployeeListSerializer

    def get(self, request):
        from tenants.models import Tenant, TenantMember
        
        # Get tenant from header
        tenant_slug = request.headers.get('X-Tenant-Slug')
        if not tenant_slug:
            return Response(
                {'error': 'X-Tenant-Slug header is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            tenant = Tenant.objects.get(slug=tenant_slug, is_active=True)
        except Tenant.DoesNotExist:
            return Response(
                {'error': 'Store not found or inactive.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if user is the store owner
        if tenant.owner != request.user:
            return Response(
                {'error': 'Only the store owner can view employees.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get all members (excluding owner)
        members = TenantMember.objects.filter(
            tenant=tenant, 
            is_active=True
        ).exclude(user=tenant.owner).select_related('user')

        users = [member.user for member in members]
        
        serializer = EmployeeListSerializer(
            users, 
            many=True, 
            context={'tenant': tenant}
        )

        return Response(
            {
                'count': len(users),
                'employees': serializer.data
            },
            status=status.HTTP_200_OK
        )


@extend_schema(
    tags=['vendor'],
    summary='Vendor - Get Employee Details',
    description='Store owner can view details of a specific employee.',
    responses={
        200: OpenApiResponse(description='Employee details retrieved successfully.'),
        403: OpenApiResponse(description='Only store owner can perform this action.'),
        404: OpenApiResponse(description='Employee not found.'),
    },
)
class VendorGetEmployeeView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EmployeeListSerializer

    def get(self, request, employee_id):
        from tenants.models import Tenant, TenantMember
        
        # Get tenant from header
        tenant_slug = request.headers.get('X-Tenant-Slug')
        if not tenant_slug:
            return Response(
                {'error': 'X-Tenant-Slug header is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            tenant = Tenant.objects.get(slug=tenant_slug, is_active=True)
        except Tenant.DoesNotExist:
            return Response(
                {'error': 'Store not found or inactive.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if user is the store owner
        if tenant.owner != request.user:
            return Response(
                {'error': 'Only the store owner can view employee details.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get the employee
        try:
            employee = User.objects.get(id=employee_id)
            member = TenantMember.objects.get(tenant=tenant, user=employee, is_active=True)
        except (User.DoesNotExist, TenantMember.DoesNotExist):
            return Response(
                {'error': 'Employee not found in this store.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = EmployeeListSerializer(employee, context={'tenant': tenant})
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(
    tags=['vendor'],
    summary='Vendor - Update Employee',
    description='Store owner can update employee details and role.',
    request=EmployeeUpdateSerializer,
    responses={
        200: OpenApiResponse(description='Employee updated successfully.'),
        400: OpenApiResponse(description='Validation error.'),
        403: OpenApiResponse(description='Only store owner can perform this action.'),
        404: OpenApiResponse(description='Employee not found.'),
    },
)
class VendorUpdateEmployeeView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EmployeeUpdateSerializer

    def patch(self, request, employee_id):
        from tenants.models import Tenant, TenantMember
        
        # Get tenant from header
        tenant_slug = request.headers.get('X-Tenant-Slug')
        if not tenant_slug:
            return Response(
                {'error': 'X-Tenant-Slug header is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            tenant = Tenant.objects.get(slug=tenant_slug, is_active=True)
        except Tenant.DoesNotExist:
            return Response(
                {'error': 'Store not found or inactive.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if user is the store owner
        if tenant.owner != request.user:
            return Response(
                {'error': 'Only the store owner can update employees.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get the employee
        try:
            employee = User.objects.get(id=employee_id)
            member = TenantMember.objects.get(tenant=tenant, user=employee, is_active=True)
        except (User.DoesNotExist, TenantMember.DoesNotExist):
            return Response(
                {'error': 'Employee not found in this store.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Don't allow updating the owner
        if employee == tenant.owner:
            return Response(
                {'error': 'Cannot update the store owner.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update employee
        serializer = EmployeeUpdateSerializer(
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        
        # Update user fields
        if 'first_name' in serializer.validated_data:
            employee.first_name = serializer.validated_data['first_name']
        if 'last_name' in serializer.validated_data:
            employee.last_name = serializer.validated_data['last_name']
        if 'is_active' in serializer.validated_data:
            employee.is_active = serializer.validated_data['is_active']
        employee.save()

        # Update member role
        if 'role' in serializer.validated_data:
            member.role = serializer.validated_data['role']
            member.save()

        # Update profile
        try:
            profile = Profile.objects.get(user=employee)
            if 'phone' in serializer.validated_data:
                profile.phone = serializer.validated_data['phone']
            if 'address' in serializer.validated_data:
                profile.address = serializer.validated_data['address']
            if 'city' in serializer.validated_data:
                profile.city = serializer.validated_data['city']
            if 'designation' in serializer.validated_data:
                profile.designation = serializer.validated_data['designation']
            if 'bio' in serializer.validated_data:
                profile.bio = serializer.validated_data['bio']
            profile.save()
        except Profile.DoesNotExist:
            pass

        return Response(
            {
                'message': 'Employee updated successfully.',
                'employee': {
                    'id': employee.id,
                    'username': employee.username,
                    'email': employee.email,
                    'first_name': employee.first_name,
                    'last_name': employee.last_name,
                    'role': member.role,
                    'is_active': employee.is_active,
                }
            },
            status=status.HTTP_200_OK
        )


@extend_schema(
    tags=['vendor'],
    summary='Vendor - Remove Employee',
    description='Store owner can remove (deactivate) an employee from their store.',
    responses={
        200: OpenApiResponse(description='Employee removed successfully.'),
        403: OpenApiResponse(description='Only store owner can perform this action.'),
        404: OpenApiResponse(description='Employee not found.'),
    },
)
class VendorRemoveEmployeeView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, employee_id):
        from tenants.models import Tenant, TenantMember
        
        # Get tenant from header
        tenant_slug = request.headers.get('X-Tenant-Slug')
        if not tenant_slug:
            return Response(
                {'error': 'X-Tenant-Slug header is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            tenant = Tenant.objects.get(slug=tenant_slug, is_active=True)
        except Tenant.DoesNotExist:
            return Response(
                {'error': 'Store not found or inactive.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if user is the store owner
        if tenant.owner != request.user:
            return Response(
                {'error': 'Only the store owner can remove employees.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get the employee
        try:
            employee = User.objects.get(id=employee_id)
            member = TenantMember.objects.get(tenant=tenant, user=employee, is_active=True)
        except (User.DoesNotExist, TenantMember.DoesNotExist):
            return Response(
                {'error': 'Employee not found in this store.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Don't allow removing the owner
        if employee == tenant.owner:
            return Response(
                {'error': 'Cannot remove the store owner.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Soft delete (deactivate)
        member.is_active = False
        member.save()
        
        # Optionally deactivate the user account
        # employee.is_active = False
        # employee.save()

        return Response(
            {
                'message': f'Employee {employee.username} has been removed from the store.',
                'employee': {
                    'id': employee.id,
                    'username': employee.username,
                    'email': employee.email,
                }
            },
            status=status.HTTP_200_OK
        )


@extend_schema(
    tags=['vendor'],
    summary='Vendor - Bulk Create Employees',
    description='Store owner can create multiple employees at once (max 50).',
    request=EmployeeBulkCreateSerializer,
    responses={
        201: OpenApiResponse(description='Employees created successfully.'),
        400: OpenApiResponse(description='Validation error.'),
        403: OpenApiResponse(description='Only store owner can perform this action.'),
    },
)
class VendorBulkCreateEmployeesView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EmployeeBulkCreateSerializer

    def post(self, request):
        from tenants.models import Tenant
        
        # Get tenant from header
        tenant_slug = request.headers.get('X-Tenant-Slug')
        if not tenant_slug:
            return Response(
                {'error': 'X-Tenant-Slug header is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            tenant = Tenant.objects.get(slug=tenant_slug, is_active=True)
        except Tenant.DoesNotExist:
            return Response(
                {'error': 'Store not found or inactive.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if user is the store owner
        if tenant.owner != request.user:
            return Response(
                {'error': 'Only the store owner can create employees.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Validate and create employees
        serializer = EmployeeBulkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        created_employees = []
        errors = []
        
        for employee_data in serializer.validated_data['employees']:
            try:
                emp_serializer = EmployeeCreateSerializer(data=employee_data)
                if emp_serializer.is_valid():
                    user, member = emp_serializer.save(
                        vendor_user=request.user,
                        tenant=tenant
                    )
                    created_employees.append({
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'role': member.role,
                    })
                else:
                    errors.append({
                        'data': employee_data,
                        'errors': emp_serializer.errors
                    })
            except Exception as e:
                errors.append({
                    'data': employee_data,
                    'error': str(e)
                })

        return Response(
            {
                'message': f'Created {len(created_employees)} employees.',
                'created': created_employees,
                'errors': errors,
                'total_attempted': len(serializer.validated_data['employees'])
            },
            status=status.HTTP_201_CREATED if created_employees else status.HTTP_400_BAD_REQUEST
        )