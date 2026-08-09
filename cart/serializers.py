from rest_framework import serializers

from .models import (
    Cart,
    CartItem,
    SavedItem,
)

from products.models import Product


# ---------------------------------------------------------
# Product Serializer (for cart context)
# ---------------------------------------------------------

class CartProductSerializer(serializers.ModelSerializer):

    vendor = serializers.CharField(
        source="tenant.name",
        read_only=True
    )

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "price",
            "quantity",
            "vendor",
        ]


# ---------------------------------------------------------
# Cart Item Serializer
# ---------------------------------------------------------

class CartItemSerializer(serializers.ModelSerializer):

    product = CartProductSerializer(read_only=True)

    subtotal = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = CartItem
        fields = [
            "id",
            "product",
            "quantity",
            "subtotal",
        ]


# ---------------------------------------------------------
# Cart Serializer
# ---------------------------------------------------------

class CartSerializer(serializers.ModelSerializer):

    items = CartItemSerializer(
        many=True,
        read_only=True
    )

    total_items = serializers.ReadOnlyField()
    subtotal = serializers.ReadOnlyField()
    discount_amount = serializers.ReadOnlyField()
    total = serializers.ReadOnlyField()

    applied_coupon_code = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            "id",
            "items",
            "total_items",
            "subtotal",
            "discount_amount",
            "total",
            "applied_coupon_code",
        ]

    def get_applied_coupon_code(self, obj):
        if obj.applied_coupon:
            return obj.applied_coupon.code
        return None


# ---------------------------------------------------------
# Add to Cart Serializer
# ---------------------------------------------------------

class AddToCartSerializer(serializers.Serializer):

    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        help_text="ID of the product to add to cart."
    )

    quantity = serializers.IntegerField(
        min_value=1,
        help_text="Quantity of the product to add."
    )


# ---------------------------------------------------------
# Update Cart Item Serializer
# ---------------------------------------------------------

class UpdateCartItemSerializer(serializers.Serializer):

    quantity = serializers.IntegerField(
        min_value=1,
        help_text="New quantity for the cart item."
    )


# ---------------------------------------------------------
# Saved Item Serializer
# ---------------------------------------------------------

class SavedItemSerializer(serializers.ModelSerializer):

    product = CartProductSerializer(read_only=True)

    subtotal = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = SavedItem
        fields = [
            "id",
            "product",
            "quantity",
            "subtotal",
            "created_at",
        ]


# ---------------------------------------------------------
# Checkout Serializer
# ---------------------------------------------------------

class CartCheckoutSerializer(serializers.Serializer):

    customer_name = serializers.CharField(
        max_length=200,
        help_text="Full name of the customer for delivery."
    )

    payment_method = serializers.ChoiceField(
        choices=[
            ("COD", "Cash on Delivery"),
            ("ESEWA", "eSewa"),
            ("KHALTI", "Khalti"),
        ],
        help_text="Payment method for the order."
    )

    delivery_city = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="City for delivery (optional if set in profile)."
    )


# ---------------------------------------------------------
# Move Saved Item to Cart Serializer
# ---------------------------------------------------------

class MoveToCartSerializer(serializers.Serializer):

    saved_item_id = serializers.IntegerField(
        help_text="ID of the saved item to move back to cart."
    )


# ---------------------------------------------------------
# Save Item for Later Serializer
# ---------------------------------------------------------

class SaveForLaterSerializer(serializers.Serializer):

    item_id = serializers.IntegerField(
        help_text="ID of the cart item to save for later."
    )