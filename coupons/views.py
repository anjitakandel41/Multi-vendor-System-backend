from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.utils import timezone

from drf_spectacular.utils import (
    extend_schema,
    OpenApiExample,
    OpenApiResponse,
)

from config.permissions import IsVendorAdmin
from tenants.mixins import TenantViewMixin

from .models import Coupon
from .serializers import (
    CouponSerializer,
    ApplyCouponSerializer,
    ValidateCouponSerializer,
)


@extend_schema(tags=["Coupons"])
class CouponViewSet(TenantViewMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing coupons with tenant isolation.

    Provides CRUD operations for vendors and public validation/application
    endpoints for authenticated users.
    """

    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer

    def get_permissions(self):
        """
        Assign permissions based on the action being performed.

        - 'apply' and 'validate' actions: Any authenticated user
        - All other actions: Only vendor admins
        """
        if self.action in ["apply", "validate"]:
            return [IsAuthenticated()]

        return [IsVendorAdmin()]

    @extend_schema(
        summary="Create Coupon",
        description="Create a new coupon. Only vendor admins can create coupons.",
        examples=[
            OpenApiExample(
                "Percentage Coupon",
                value={
                    "code": "SAVE20",
                    "discount_type": "percentage",
                    "discount_value": "20.00",
                    "minimum_order_amount": "1000.00",
                    "max_uses": 100,
                    "is_active": True,
                    "expires_at": "2026-12-31T00:00:00Z",
                },
                request_only=True,
            )
        ],
    )
    def create(self, request, *args, **kwargs):
        """
        Create a new coupon.

        Overridden to add OpenAPI schema documentation only.
        All logic is handled by the parent ModelViewSet.
        """
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Validate Coupon",
        description="Checks whether a coupon is valid without applying it. "
                    "Validates the coupon code, expiration date, and usage limits.",
        request=ValidateCouponSerializer,
        responses={
            200: OpenApiResponse(description="Coupon is valid."),
            400: OpenApiResponse(description="Invalid coupon or validation failed."),
        },
    )
    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsAuthenticated],
    )
    def validate(self, request):
        """
        Validate a coupon code without applying it.

        Returns coupon details if valid, or error if invalid.
        """
        serializer = ValidateCouponSerializer(
            data=request.data,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)

        coupon = serializer.validated_data["coupon"]

        return Response(
            {
                "valid": True,
                "coupon": coupon.code,
                "discount_type": coupon.discount_type,
                "discount_value": coupon.discount_value,
                "minimum_order_amount": coupon.minimum_order_amount,
                "expires_at": coupon.expires_at,
                "message": "Coupon is valid.",
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Expired Coupons",
        description="Returns all expired coupons. Only vendor admins can access.",
        responses={
            200: OpenApiResponse(description="List of expired coupons."),
        },
    )
    @action(
        detail=False,
        methods=["get"],
    )
    def expired(self, request):
        """
        Retrieve all coupons that have expired.

        Filters coupons where expires_at is less than current time.
        """
        coupons = self.get_queryset().filter(
            expires_at__lt=timezone.now()
        )

        serializer = self.get_serializer(
            coupons,
            many=True,
        )

        return Response(serializer.data)

    @extend_schema(
        summary="Apply Coupon",
        description="Apply a coupon to an order and calculate the discount. "
                    "Returns the original amount, discount amount, and final amount.",
        request=ApplyCouponSerializer,
        responses={
            200: OpenApiResponse(
                description="Coupon applied successfully.",
                examples=[
                    OpenApiExample(
                        "Success Response",
                        value={
                            "code": "SAVE20",
                            "discount_type": "percentage",
                            "discount_value": "20.00",
                            "discount_amount": "1000.00",
                            "original_amount": "5000.00",
                            "final_amount": "4000.00",
                            "message": "Coupon applied! You saved NPR 1000.00.",
                        },
                        response_only=True,
                    )
                ]
            ),
            400: OpenApiResponse(description="Invalid coupon or order amount."),
        },
        examples=[
            OpenApiExample(
                "Apply Coupon",
                value={
                    "code": "SAVE20",
                    "order_amount": "5000.00",
                },
                request_only=True,
            )
        ],
    )
    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsAuthenticated],
    )
    def apply(self, request):
        """
        Apply a coupon to an order and calculate the discounted amount.

        Validates the coupon and calculates the discount based on the
        coupon type (percentage or fixed amount).
        """
        serializer = ApplyCouponSerializer(
            data=request.data,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)

        coupon = serializer.validated_data["coupon"]

        return Response(
            {
                "code": coupon.code,
                "discount_type": coupon.discount_type,
                "discount_value": str(coupon.discount_value),
                "discount_amount": str(serializer.validated_data["discount"]),
                "original_amount": str(serializer.validated_data["order_amount"]),
                "final_amount": str(serializer.validated_data["final_amount"]),
                "message": f"Coupon applied! You saved NPR {serializer.validated_data['discount']}.",
            },
            status=status.HTTP_200_OK,
        )