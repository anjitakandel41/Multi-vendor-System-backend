from rest_framework.exceptions import PermissionDenied, ValidationError


class TenantViewMixin:
    """
    Mixin to make ViewSets and APIViews tenant-aware.

    Features:
    - Automatically filters get_queryset() to the current tenant
    - Automatically assigns tenant on perform_create()
    - Provides get_tenant() with fallback resolution logic
    - Raises 403 if no valid tenant can be identified
    """

    def get_tenant(self):
        """
        Resolve and return the current tenant for this request.
        
        Resolution order:
        1. Check if tenant is already attached to request
        2. Try X-Tenant-Slug header
        3. Try tenant query parameter
        4. Raise PermissionDenied if none found
        
        Note: Uses explicit tenant checking to properly evaluate the 
        SimpleLazyObject wrapper.
        """
        tenant = getattr(self.request, 'tenant', None)

        if tenant:
            return tenant

        # Attempt to resolve from headers or query params
        tenant_slug = (
            self.request.headers.get("X-Tenant-Slug")
            or self.request.query_params.get("tenant")
        )

        if tenant_slug:
            from tenants.models import Tenant

            tenant = Tenant.objects.filter(
                slug=tenant_slug,
                is_active=True,
                status=Tenant.STATUS_APPROVED
            ).first()

            if tenant:
                return tenant

        raise PermissionDenied(
            'Unable to identify tenant. '
            'Please provide X-Tenant-Slug header or log in as a vendor.'
        )

    def get_queryset(self):
        """
        Filter queryset to only include objects belonging to the current tenant.
        Uses explicit tenant check to properly evaluate the SimpleLazyObject.
        """
        queryset = super().get_queryset()
        tenant = getattr(self.request, 'tenant', None)
        
        # Explicit truthiness check forces SimpleLazyObject evaluation
        # Using `is not None` would always be True since request.tenant
        # is always a SimpleLazyObject instance
        if tenant:
            return queryset.filter(tenant=tenant)
        return queryset

    def perform_create(self, serializer):
        """
        Automatically assign the current tenant when creating new objects.
        """
        tenant = self.get_tenant()
        serializer.save(tenant=tenant)