from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CouponViewSet

# Initialize the default router
router = DefaultRouter()

# Register the CouponViewSet with the router
# URL pattern: /api/coupons/
router.register('coupons', CouponViewSet, basename='coupons')

# URL patterns for the coupon app
urlpatterns = [
    path('', include(router.urls)),
]
