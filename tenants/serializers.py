from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Tenant, TenantMember

User = get_user_model()


class TenantSerializer(serializers.ModelSerializer):

    owner_username = serializers.CharField(source='owner.username', read_only=True)
    owner_email = serializers.CharField(source='owner.email', read_only=True)

    class Meta:
        model = Tenant
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'owner',
            'owner_username',
            'owner_email',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TenantMemberSerializer(serializers.ModelSerializer):
    """
    Serializer for store team members.
    - Read: Returns username, email, role, and status
    - Create: Accepts 'add_user' (username) + role
    - Update: Allows modifying 'role' and 'is_active'
    """
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    add_user = serializers.CharField(
        write_only=True,
        required=False,
        help_text='Username of the user to add as a team member.',
    )

    class Meta:
        model = TenantMember
        fields = ['id', 'add_user', 'username', 'email', 'role', 'is_active', 'created_at']
        read_only_fields = ['id', 'username', 'email', 'created_at']

    def validate_add_user(self, value):
        try:
            return User.objects.get(username=value)
        except User.DoesNotExist:
            raise serializers.ValidationError(f'No user found with username "{value}".')

    def validate(self, data):
        if self.instance is None and 'add_user' not in data:
            raise serializers.ValidationError({'add_user': 'This field is required when adding a new member.'})
        return data

    def create(self, validated_data):
        user = validated_data.pop('add_user')
        tenant = self.context['tenant']

        if tenant.owner == user:
            raise serializers.ValidationError({'add_user': 'User is already the store owner.'})

        member, created = TenantMember.objects.get_or_create(
            tenant=tenant,
            user=user,
            defaults={
                'role': validated_data.get('role', TenantMember.ROLE_STAFF),
                'is_active': True,
            }
        )
        if not created:
            # Reactivate an existing member if they were previously deactivated
            member.role = validated_data.get('role', member.role)
            member.is_active = True
            member.save()
        return member


class TenantLoginSerializer(serializers.Serializer):
    """
    Authenticate users for tenant-specific access:
    - Store owners
    - Team members (manager, staff, viewer)

    Returns JWT tokens along with tenant information and the user's role.
    The client must store tenant_slug and include it in the
    X-Tenant-Slug header for all subsequent store API calls.
    """
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    tenant_slug = serializers.SlugField(
        help_text='Store slug for login (e.g., electrohub).'
    )

    def validate(self, attrs):
        user = authenticate(username=attrs['username'], password=attrs['password'])
        if not user:
            raise serializers.ValidationError({'username': 'Invalid credentials provided.'})
        if not user.is_email_verified:
            raise serializers.ValidationError({'username': 'Please verify your email before logging in.'})

        try:
            tenant = Tenant.objects.get(slug=attrs['tenant_slug'], is_active=True)
        except Tenant.DoesNotExist:
            raise serializers.ValidationError({'tenant_slug': 'Store not found or currently inactive.'})

        # Determine the user's role within this tenant
        tenant_role = None
        try:
            if user.owned_tenant == tenant:
                tenant_role = 'owner'
        except Exception:
            pass

        if tenant_role is None:
            try:
                membership = TenantMember.objects.get(
                    tenant=tenant, user=user, is_active=True
                )
                tenant_role = membership.role
            except TenantMember.DoesNotExist:
                raise serializers.ValidationError({
                    'tenant_slug': (
                        'You do not have access to this store. '
                        'Please contact the store owner to add you via /api/tenant-members/.'
                    )
                })

        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
            },
            'tenant': {
                'id': tenant.id,
                'name': tenant.name,
                'slug': tenant.slug,
            },
            'tenant_role': tenant_role,
            'next_step': f'Include X-Tenant-Slug: {tenant.slug} in all subsequent API requests.',
        }