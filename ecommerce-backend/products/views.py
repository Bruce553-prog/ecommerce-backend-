from django.conf import settings
from django.db import IntegrityError
from rest_framework import viewsets, permissions, filters, status
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Category, Product, Review
from .filters import ProductFilter
from users.permissions import IsAdminOrReadOnly, IsVendorOrReadOnly
from .serializers import (
    CategorySerializer,
    ProductSerializer,
    ProductWriteSerializer,
    ReviewSerializer
)

# Actions that change or remove an existing product.
WRITE_ACTIONS = ('update', 'partial_update', 'destroy')


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by('name')
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]


class ProductViewSet(viewsets.ModelViewSet):
    filterset_class = ProductFilter
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description', 'category__name', 'tags']
    ordering_fields = ['price', 'created_at']
    # JSONParser added so review requests sent as JSON are accepted (images still use multipart).
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    # Must exist on the class so individual actions can set their own throttle_scope.
    throttle_scope = None

    def get_queryset(self):
        queryset = (
            Product.objects.filter(is_active=True)
            .select_related('category')
            .prefetch_related('images', 'reviews__customer')  # customer: avoids one query per review
            .order_by('-created_at')  # fixed order, so paging never repeats or skips items
        )

        # Changing or deleting a product: only the person who created it (or staff) can reach it.
        # Anyone else gets "not found", exactly as if the product didn't exist.
        if self.action in WRITE_ACTIONS:
            user = self.request.user
            if not user.is_authenticated:
                return queryset.none()
            if not user.is_staff:
                queryset = queryset.filter(created_by=user)

        return queryset

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ProductWriteSerializer
        return ProductSerializer

    def get_permissions(self):
        # Every action is listed here on purpose, so none can end up with the wrong rule.
        if self.action in ('list', 'retrieve', 'by_category', 'reviews'):
            return [permissions.AllowAny()]
        if self.action in ('add_review', 'delete_review'):
            return [permissions.IsAuthenticated()]
        return [IsVendorOrReadOnly()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_destroy(self, instance):
        # Hide the product instead of deleting it. A real delete would also wipe it from
        # past orders and change their totals. Hidden products can't be bought.
        instance.is_active = False
        instance.save(update_fields=['is_active'])

    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """Filter products by category slug."""
        slug = request.query_params.get('slug')
        if not slug:
            return Response({"error": "slug parameter is required."}, status=400)
        products = self.get_queryset().filter(category__slug=slug)
        serializer = ProductSerializer(products, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        """Get all reviews for a product."""
        product = self.get_object()
        reviews = product.reviews.all().order_by('-id')
        serializer = ReviewSerializer(reviews, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'], throttle_scope='review')
    def add_review(self, request, pk=None):
        """Add a review for a product."""
        product = self.get_object()

        # Sellers can't review their own products.
        # getattr so this keeps working even before the created_by field is added to the model.
        if getattr(product, 'created_by_id', None) == request.user.id:
            return Response(
                {"error": "You can't review your own product."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if user already reviewed this product
        if Review.objects.filter(product=product, customer=request.user).exists():
            return Response(
                {"error": "You have already reviewed this product."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ReviewSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save(product=product, customer=request.user)
        except IntegrityError:
            # Two requests at the same moment: the database blocked the duplicate.
            return Response(
                {"error": "You have already reviewed this product."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'])
    def delete_review(self, request, pk=None):
        """Delete own review."""
        product = self.get_object()
        try:
            review = Review.objects.get(product=product, customer=request.user)
            review.delete()
            return Response({"detail": "Review deleted."})
        except Review.DoesNotExist:
            return Response(
                {"error": "You have not reviewed this product."},
                status=status.HTTP_404_NOT_FOUND
            )