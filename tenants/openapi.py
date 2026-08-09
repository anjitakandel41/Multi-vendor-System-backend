def add_tenant_auth_to_schema(result, generator, request, public):
    """
    DRF Spectacular post-processing hook that adds X-Tenant-Slug 
    as a security scheme in the Swagger UI.

    This enables the tenant header to appear in the Authorize dialog 
    alongside the JWT authentication field in the API documentation.

    Usage: After login, users copy the tenant.slug from the response
    and paste it here once - all subsequent requests will include it automatically.
    """
    components = result.setdefault('components', {})
    schemes = components.setdefault('securitySchemes', {})

    # Register the tenant authentication scheme
    schemes['tenantAuth'] = {
        'type': 'apiKey',
        'in': 'header',
        'name': 'X-Tenant-Slug',
        'description': (
            'Your store identifier slug (e.g., **electrohub**). '
            'This value is provided in the login response under `tenant.slug`. '
            'Required for all tenant-scoped endpoints (products, warehouses, '
            'inventory management, orders, etc.).'
        ),
    }

    # Apply tenant authentication globally so all endpoints display 
    # both security locks in the Swagger UI interface
    security = result.setdefault('security', [])
    if {'tenantAuth': []} not in security:
        security.append({'tenantAuth': []})

    return result