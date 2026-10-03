import os

from django.db import transaction
from rest_framework import serializers
from .models import Category, Product, ProductImage, Review

MAX_IMAGES_PER_PRODUCT = 8
MAX_IMAGE_MB = 5
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description']
        read_only_fields = ['slug']


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'is_primary', 'alt_text']


class ReviewSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.username', read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'customer_name', 'rating', 'comment', 'created_at']
        read_only_fields = ['customer_name', 'created_at']
        # The comment box had no length limit at all.
        extra_kwargs = {'comment': {'max_length': 2000}}

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value


class ProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    reviews = ReviewSerializer(many=True, read_only=True)
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'description',
            'price', 'stock', 'is_active',
            'category', 'category_name',
            'video',
            'images', 'tags', 'specifications', 'reviews',
            'average_rating', 'review_count',
            'created_at', 'updated_at', 'demo_video',
        ]
        read_only_fields = ['slug', 'created_at', 'updated_at']

    def get_average_rating(self, obj):
        return obj.average_rating()

    def get_review_count(self, obj):
        return obj.review_count()

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value

    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("Stock cannot be negative.")
        return value


class ProductWriteSerializer(serializers.ModelSerializer):
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = Product
        fields = [
            'id', 'slug',
            'name', 'description', 'price',
            'stock', 'is_active', 'category',
            'tags', 'uploaded_images'
        ]
        read_only_fields = ['id', 'slug']
        extra_kwargs = {'description': {'max_length': 5000}}

    # These two checks used to live only on the read-only serializer, so they never
    # ran when a product was created or edited. A negative price could be saved.
    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value

    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("Stock cannot be negative.")
        return value

    def validate_uploaded_images(self, images):
        if len(images) > MAX_IMAGES_PER_PRODUCT:
            raise serializers.ValidationError(
                f"You can upload at most {MAX_IMAGES_PER_PRODUCT} images at a time."
            )
        for image in images:
            if image.size > MAX_IMAGE_MB * 1024 * 1024:
                raise serializers.ValidationError(
                    f"'{image.name}' is too large. Maximum size is {MAX_IMAGE_MB} MB."
                )
            ext = os.path.splitext(image.name)[1].lower()
            if ext not in ALLOWED_IMAGE_EXTENSIONS:
                raise serializers.ValidationError(
                    f"'{image.name}': only JPG, PNG or WEBP images are allowed."
                )
        return images

    def create(self, validated_data):
        images = validated_data.pop('uploaded_images', [])
        with transaction.atomic():
            product = Product.objects.create(**validated_data)
            for i, image in enumerate(images):
                ProductImage.objects.create(
                    product=product,
                    image=image,
                    is_primary=(i == 0)
                )
        return product

    def update(self, instance, validated_data):
        # New images are added to the existing ones. Before, images sent while editing
        # were silently ignored.
        images = validated_data.pop('uploaded_images', [])
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            has_primary = instance.images.filter(is_primary=True).exists()
            for i, image in enumerate(images):
                ProductImage.objects.create(
                    product=instance,
                    image=image,
                    is_primary=(not has_primary and i == 0)
                )
        return instance