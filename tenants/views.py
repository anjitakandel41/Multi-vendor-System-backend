from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter, OpenApiResponse

from config.permissions import IsPlatformAdmin, IsTenantOwner
from .models import Tenant, TenantMember
from .serializers import TenantSerializer, TenantMemberSerializer


# ── Tenant Management (Platform Admin Only) ────────────────────────────────────

class TenantViewSet(viewsets.ModelViewSet):
    """
    Complete CRUD operations for Tenant (vendor stores) management.

    Access Control:
      - Platform administrators (is_staff=True) — full CRUD + approval workflow
      - Authenticated users — GET /api/tenants/me/ to view their own store

    Filter pending registrations: GET /api/tenants/?is_active=false
    """
    queryset = Tenant.objects.select_related('owner').order_by('name')
    serializer_class = TenantSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'slug', 'owner__username', 'owner__email']
    ordering_fields = ['name', 'created_at']

    def get_permissions(self):
        if self.action == 'me':
            return [IsAuthenticated()]
        return [IsPlatformAdmin()]

    @extend_schema(
        summary='Get all vendor stores',
        description=(
            'Retrieves a complete list of vendor stores. '
            'Use `?is_active=false` to view pending approval registrations.'
        ),
        parameters=[
            OpenApiParameter('is_active', bool, description='Filter by active status. false = pending stores.'),
            OpenApiParameter('search', str, description='Search by name, slug, or owner credentials.'),
        ],
        tags=['Tenants'],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary='Create a new store (admin)',
        description='Admin-only endpoint for manual store registration. Users should use vendor/register for self-registration.',
        tags=['Tenants'],
        examples=[
            OpenApiExample(
                name='Store Creation Example',
                value={
                    'name': 'ElectroHub Nepal',
                    'slug': 'electrohub',
                    'description': 'Premium electronics and gadgets store.',
                    'owner': 1,
                    'is_active': True,
                },
                request_only=True,
            )
        ]
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(summary='Get store details', tags=['Tenants'])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(summary='Full store update', tags=['Tenants'])
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(summary='Partial store update', tags=['Tenants'])
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(summary='Remove a store', tags=['Tenants'])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary='Get my store',
        description='Returns the store belonging to the currently authenticated vendor.',
        responses={200: TenantSerializer},
        tags=['Tenants'],
    )
    @action(detail=False, methods=['get'], url_path='me')
    def me(self, request):
        try:
            tenant = request.user.owned_tenant
        except Tenant.DoesNotExist:
            return Response(
                {'error': 'No store associated with your account.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(TenantSerializer(tenant).data)

    @extend_schema(
        summary='Approve pending store',
        description=(
            'Activates a vendor store that is awaiting approval. '
            'Once approved, the vendor gains full access to the platform.'
        ),
        request=None,
        responses={
            200: OpenApiResponse(description='Store successfully activated.'),
            400: OpenApiResponse(description='Store is already active.'),
        },
        tags=['Tenants'],
    )
    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        tenant = self.get_object()
        if tenant.is_active:
            return Response(
                {'detail': 'This store is already active.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tenant.is_active = True
        tenant.save(update_fields=['is_active'])
        return Response(
            {
                'detail': f'Store "{tenant.name}" has been approved and activated.',
                'store': {
                    'id': tenant.id,
                    'name': tenant.name,
                    'slug': tenant.slug,
                },
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary='Reject pending store',
        description=(
            'Rejects and deletes a vendor store registration. '
            'The vendor account remains active for future re-applications. '
            'Only applies to inactive (pending) stores.'
        ),
        request=None,
        responses={
            200: OpenApiResponse(description='Store registration rejected and removed.'),
            400: OpenApiResponse(description='Cannot reject an active store.'),
        },
        tags=['Tenants'],
    )
    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        tenant = self.get_object()
        if tenant.is_active:
            return Response(
                {
                    'detail': (
                        'This store is already active. '
                        'Use DELETE /api/tenants/{id}/ to remove an active store.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        owner_username = tenant.owner.username
        store_name = tenant.name
        tenant.delete()
        return Response(
            {
                'detail': (
                    f'Store "{store_name}" (owner: {owner_username}) has been rejected and removed. '
                    f'The owner can re-apply for store registration.'
                )
            },
            status=status.HTTP_200_OK,
        )


# ── Team Member Management (Store Owner Only) ────────────────────────────────

class TenantMemberViewSet(viewsets.ModelViewSet):
    """
    Manage your store's team members and their roles.

    Authorization: Only the store owner can manage team members.
    Header Requirement: X-Tenant-Slug must be provided.

    Available Roles:
      manager — Full store access (products, warehouses, inventory, coupons, orders)
      staff   — Manage inventory and view orders
      viewer  — Read-only access to store data
    """
    serializer_class = TenantMemberSerializer
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_permissions(self):
        return [IsTenantOwner()]

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return TenantMember.objects.none()
        return TenantMember.objects.filter(tenant=tenant).select_related('user')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['tenant'] = getattr(self.request, 'tenant', None)
        return ctx

    @extend_schema(
        summary='List all team members',
        description='Get a complete list of all members associated with your store.',
        tags=['Team Members'],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary='Add team member',
        description=(
            'Add an existing platform user to your store with a specific role. '
            'The user must already have a registered account.'
        ),
        request=TenantMemberSerializer,
        tags=['Team Members'],
        examples=[
            OpenApiExample(
                name='Add manager',
                value={'add_user': 'john_doe', 'role': 'manager'},
                request_only=True,
            ),
            OpenApiExample(
                name='Add staff',
                value={'add_user': 'jane_smith', 'role': 'staff'},
                request_only=True,
            ),
            OpenApiExample(
                name='Add viewer',
                value={'add_user': 'bob_viewer', 'role': 'viewer'},
                request_only=True,
            ),
        ]
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary='Update member role',
        description="Modify a team member's role or toggle their active status.",
        request=TenantMemberSerializer,
        tags=['Team Members'],
        examples=[
            OpenApiExample(
                name='Promote to manager',
                value={'role': 'manager'},
                request_only=True,
            ),
            OpenApiExample(
                name='Deactivate member',
                value={'is_active': False},
                request_only=True,
            ),
        ]
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary='Remove team member',
        description='Remove a user from your store team.',
        tags=['Team Members'],
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)