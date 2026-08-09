from django.utils.functional import SimpleLazyObject
from tenants.models import Tenant, TenantMember


def _get_tenant_from_request(request):
    """
    Resolve the tenant from the request in order of priority:
    1. X-Tenant-Slug header
    2. tenant query parameter
    3. User's owned tenant (if authenticated)
    """
    tenant_slug = request.headers.get("X-Tenant-Slug") or request.GET.get("tenant")

    if tenant_slug:
        return Tenant.objects.filter(slug=tenant_slug, is_active=True).first()

    if request.user.is_authenticated:
        return getattr(request.user, "owned_tenant", None)

    return None


class TenantMiddleware:
    """
    Middleware that attaches the current tenant to the request object.
    The tenant is resolved lazily to avoid unnecessary database queries.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Attach tenant as a lazy object - resolves only when accessed
        request.tenant = SimpleLazyObject(lambda: _get_tenant_from_request(request))
        return self.get_response(request)