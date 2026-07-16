# accounts/serializers.py
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Profile

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'date_joined', 'last_login']
        read_only_fields = ['id', 'date_joined', 'last_login']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']
        read_only_fields = ['id']

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Username already exists.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email already exists.')
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            role='customer'
        )
        Profile.objects.create(user=user)
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            username=attrs.get('username'),
            password=attrs.get('password')
        )
        if not user:
            raise serializers.ValidationError('Invalid username or password.')

        if not user.is_email_verified:
            raise serializers.ValidationError('Email is not verified.')

        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
            }
        }


class AdminLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            username=attrs.get('username'),
            password=attrs.get('password')
        )
        if not user:
            raise serializers.ValidationError('Invalid username or password.')
        if user.role != 'admin':
            raise serializers.ValidationError('Admin access only.')
        if not user.is_email_verified:
            raise serializers.ValidationError('Email is not verified.')

        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
            }
        }


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Old password is incorrect.')
        return value

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': 'Passwords do not match.'
            })
        if data['old_password'] == data['new_password']:
            raise serializers.ValidationError({
                'new_password': 'New password must be different from old password.'
            })
        return data

    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(help_text='Refresh token to blacklist.')


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    role = serializers.CharField(source='user.role', read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            'id', 'username', 'email', 'role', 'avatar', 'avatar_url',
            'phone', 'address', 'city', 'bio', 'designation',
            'date_of_birth', 'gender', 'emergency_contact', 'emergency_contact_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'avatar_url']
        extra_kwargs = {'avatar': {'write_only': True}}

    def get_avatar_url(self, obj):
        return obj.get_avatar_url()

    def validate_avatar(self, value):
        if value:
            if hasattr(value, 'size') and value.size > 2 * 1024 * 1024:
                raise serializers.ValidationError('Avatar size must not exceed 2MB.')
            if hasattr(value, 'content_type'):
                allowed = ['image/jpeg', 'image/png', 'image/webp']
                if value.content_type not in allowed:
                    raise serializers.ValidationError('Only JPEG, PNG, and WebP images are allowed.')
        return value


class VendorRegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    store_name = serializers.CharField(max_length=255)
    store_slug = serializers.SlugField(max_length=100)
    store_description = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('This username is already taken.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value

    def validate_store_slug(self, value):
        from tenants.models import Tenant
        if Tenant.objects.filter(slug=value).exists():
            raise serializers.ValidationError('A store with this slug already exists.')
        return value

    def validate_store_name(self, value):
        from tenants.models import Tenant
        if Tenant.objects.filter(name=value).exists():
            raise serializers.ValidationError('A store with this name already exists.')
        return value

    def create(self, validated_data):
        from django.db import transaction
        from tenants.models import Tenant

        with transaction.atomic():
            user = User.objects.create_user(
                username=validated_data['username'],
                email=validated_data['email'],
                password=validated_data['password'],
                role='admin',
            )
            user.is_email_verified = True
            user.save()
            Profile.objects.create(user=user)

            tenant = Tenant.objects.create(
                name=validated_data['store_name'],
                slug=validated_data['store_slug'],
                description=validated_data.get('store_description', ''),
                owner=user,
                is_active=False,
            )

        return user, tenant


class VendorLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(username=attrs['username'], password=attrs['password'])
        if not user:
            raise serializers.ValidationError({'username': 'Invalid username or password.'})
        if not user.is_email_verified:
            raise serializers.ValidationError({'username': 'Email is not verified.'})
        if user.role != 'admin':
            raise serializers.ValidationError({'username': 'This account does not have vendor admin access.'})

        try:
            tenant = user.owned_tenant
        except Exception:
            raise serializers.ValidationError({
                'username': 'No store found for this account.'
            })

        if not tenant.is_active:
            raise serializers.ValidationError({
                'username': 'Your store is pending approval.'
            })

        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
            },
            'store': {
                'id': tenant.id,
                'name': tenant.name,
                'slug': tenant.slug,
                'your_role': 'owner',
            }
        }


class EmployeeLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    tenant_slug = serializers.SlugField()

    def validate(self, attrs):
        user = authenticate(username=attrs['username'], password=attrs['password'])
        if not user:
            raise serializers.ValidationError({'username': 'Invalid username or password.'})
        if not user.is_email_verified:
            raise serializers.ValidationError({'username': 'Email is not verified.'})

        from tenants.models import Tenant, TenantMember

        try:
            tenant = Tenant.objects.get(slug=attrs['tenant_slug'], is_active=True)
        except Tenant.DoesNotExist:
            raise serializers.ValidationError({'tenant_slug': 'Store not found or inactive.'})

        # Check if user is the owner (they should use vendor login)
        try:
            if user.owned_tenant == tenant:
                raise serializers.ValidationError({
                    'username': 'You are the store owner. Please use vendor login.'
                })
        except:
            pass

        try:
            membership = TenantMember.objects.get(tenant=tenant, user=user, is_active=True)
        except TenantMember.DoesNotExist:
            raise serializers.ValidationError({
                'tenant_slug': 'You are not a member of this store.'
            })

        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
            },
            'store': {
                'id': tenant.id,
                'name': tenant.name,
                'slug': tenant.slug,
                'your_role': membership.role,
            }
        }


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("No user found with this email address.")
        return value


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': 'Passwords do not match.'
            })
        return data

    def validate_token(self, value):
        try:
            user = User.objects.get(reset_password_token=value)
            if not user.is_reset_token_valid():
                raise serializers.ValidationError(
                    "This password reset link has expired. Please request a new one."
                )
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid reset token.")
        return value

    def save(self):
        token = self.validated_data['token']
        new_password = self.validated_data['new_password']
        
        try:
            user = User.objects.get(reset_password_token=token)
            user.set_password(new_password)
            user.reset_password_token = None
            user.reset_password_token_created_at = None
            user.save()
            return user
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid reset token.")


# ============================================
# VENDOR EMPLOYEE MANAGEMENT SERIALIZERS
# ============================================

class EmployeeCreateSerializer(serializers.Serializer):
    """
    Serializer for vendor to create employee accounts
    """
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    role = serializers.ChoiceField(
        choices=['manager', 'staff', 'viewer'],
        default='staff',
        help_text="Employee role in the store"
    )
    phone = serializers.CharField(required=False, allow_blank=True)
    designation = serializers.CharField(required=False, allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Username already exists.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email already exists.')
        return value

    def save(self, vendor_user, tenant):
        from django.db import transaction
        from tenants.models import TenantMember
        
        with transaction.atomic():
            # Create user
            user = User.objects.create_user(
                username=self.validated_data['username'],
                email=self.validated_data['email'],
                password=self.validated_data['password'],
                first_name=self.validated_data.get('first_name', ''),
                last_name=self.validated_data.get('last_name', ''),
                role='customer',
                is_email_verified=True,
            )
            
            # Create profile with additional fields
            profile = Profile.objects.create(
                user=user,
                phone=self.validated_data.get('phone', ''),
                designation=self.validated_data.get('designation', '')
            )
            
            # Add to tenant as employee
            tenant_member = TenantMember.objects.create(
                tenant=tenant,
                user=user,
                role=self.validated_data.get('role', 'staff'),
                added_by=vendor_user,
                is_active=True,
            )
            
            return user, tenant_member


class EmployeeListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing employees
    """
    role = serializers.SerializerMethodField()
    added_by = serializers.SerializerMethodField()
    profile_avatar = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    designation = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'role', 'is_active', 'is_email_verified', 'profile_avatar', 
            'date_joined', 'last_login', 'added_by', 'phone', 'designation'
        ]

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_role(self, obj):
        tenant = self.context.get('tenant')
        if tenant:
            from tenants.models import TenantMember
            try:
                member = TenantMember.objects.get(tenant=tenant, user=obj)
                return member.role
            except TenantMember.DoesNotExist:
                return None
        return None

    def get_added_by(self, obj):
        tenant = self.context.get('tenant')
        if tenant:
            from tenants.models import TenantMember
            try:
                member = TenantMember.objects.get(tenant=tenant, user=obj)
                if member.added_by:
                    return {
                        'id': member.added_by.id,
                        'username': member.added_by.username,
                        'email': member.added_by.email,
                    }
            except TenantMember.DoesNotExist:
                pass
        return None

    def get_profile_avatar(self, obj):
        try:
            return obj.profile.get_avatar_url()
        except:
            return None

    def get_phone(self, obj):
        try:
            return obj.profile.phone
        except:
            return None

    def get_designation(self, obj):
        try:
            return obj.profile.designation
        except:
            return None


class EmployeeUpdateSerializer(serializers.Serializer):
    """
    Serializer for vendor to update employee details
    """
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    role = serializers.ChoiceField(
        choices=['manager', 'staff', 'viewer'],
        required=False
    )
    is_active = serializers.BooleanField(required=False)
    phone = serializers.CharField(required=False)
    address = serializers.CharField(required=False)
    city = serializers.CharField(required=False)
    designation = serializers.CharField(required=False)
    bio = serializers.CharField(required=False)


class EmployeeBulkCreateSerializer(serializers.Serializer):
    """
    Serializer for bulk employee creation
    """
    employees = serializers.ListField(
        child=EmployeeCreateSerializer(),
        min_length=1,
        max_length=50,
        help_text="List of employees to create (max 50)"
    )


class EmployeeActivityLogSerializer(serializers.ModelSerializer):
    """
    Serializer for employee activity logs
    """
    employee_name = serializers.CharField(source='employee.username', read_only=True)
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)

    class Meta:
        from .models import EmployeeActivityLog
        model = EmployeeActivityLog
        fields = [
            'id', 'employee', 'employee_name', 'tenant', 'tenant_name',
            'action', 'resource_type', 'resource_id', 'details',
            'ip_address', 'user_agent', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class EmployeeInvitationSerializer(serializers.ModelSerializer):
    """
    Serializer for employee invitations
    """
    invited_by_name = serializers.CharField(source='invited_by.username', read_only=True)
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)

    class Meta:
        from .models import EmployeeInvitation
        model = EmployeeInvitation
        fields = [
            'id', 'email', 'tenant', 'tenant_name', 'invited_by', 'invited_by_name',
            'role', 'token', 'status', 'created_at', 'expires_at', 'accepted_at'
        ]
        read_only_fields = ['id', 'token', 'created_at', 'expires_at']