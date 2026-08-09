from rest_framework import viewsets, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework import filters

from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse

from tenants.mixins import TenantViewMixin
from .models import Review
from .serializers import ReviewReadSerializer, ReviewWriteSerializer
from orders.models import Order  # Assuming you have an Order model

@extend_schema(tags=['reviews'])
class ReviewViewSet(TenantViewMixin, viewsets.ModelViewSet):
    queryset = Review.objects.select_related('user', 'product')
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['rating', 'created_at']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return ReviewReadSerializer
        return ReviewWriteSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        product_id = self.request.query_params.get('product')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return queryset

    def perform_create(self, serializer):
        product = serializer.validated_data['product']
        user = self.request.user
        
        # Check if user purchased the product
        if not Order.objects.filter(
            user=user, 
            product=product, 
            status='completed'
        ).exists():
            raise PermissionDenied(
                "You can only review products you have purchased"
            )
        
        # Check if user already reviewed this product
        if Review.objects.filter(user=user, product=product).exists():
            raise PermissionDenied(
                "You have already reviewed this product"
            )
        
        # Check if user is not the seller
        if product.seller == user:
            raise PermissionDenied(
                "You cannot review your own products"
            )
        
        serializer.save(user=user)

    @extend_schema(
        summary='List all reviews',
        description='Filter by product using ?product=<id>',
        responses=ReviewReadSerializer,
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary='Write a review (Authenticated)',
        description='Only customers who purchased the product can review it.',
        request=ReviewWriteSerializer,
        examples=[
            OpenApiExample(
                name='Review Example',
                value={
                    'product': 1,
                    'rating': 5,
                    'comment': 'Great product, very fast delivery!',
                },
                request_only=True,
            )
        ]
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary='Update your review',
        request=ReviewWriteSerializer,
        examples=[
            OpenApiExample(
                name='Update Review Example',
                value={
                    'rating': 4,
                    'comment': 'Updated my review after using it more.',
                },
                request_only=True,
            )
        ]
    )
    def partial_update(self, request, *args, **kwargs):
        review = self.get_object()
        if review.user != request.user:
            return Response(
                {'error': 'You can only edit your own reviews.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary='Delete a review',
        description='Delete your own review or any review if admin',
        responses={
            204: OpenApiResponse(description='Review deleted successfully'),
            403: OpenApiResponse(description='Permission denied'),
            404: OpenApiResponse(description='Review not found'),
        }
    )
    def destroy(self, request, *args, **kwargs):
        review = self.get_object()
        if review.user != request.user and request.user.role != 'admin':
            return Response(
                {'error': 'You can only delete your own reviews.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)