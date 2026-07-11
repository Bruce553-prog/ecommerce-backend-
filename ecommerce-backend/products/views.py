from django.conf import settings
from rest_framework import viewsets, permissions, filters, status
from rest_framework.parsers import MultiPartParser, FormParser
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


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]


class ProductViewSet(viewsets.ModelViewSet):
    filterset_class = ProductFilter
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description', 'category__name', 'tags']
    ordering_fields = ['price', 'created_at']
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_vendor:
            if self.action in ['update', 'partial_update', 'destroy']:
                return Product.objects.filter(
                    is_active=True,
                    created_by=self.request.user
                ).select_related('category').prefetch_related('images', 'reviews')
        return Product.objects.filter(
            is_active=True
        ).select_related('category').prefetch_related('images', 'reviews')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ProductWriteSerializer
        return ProductSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'by_category', 'reviews']:
            return [permissions.AllowAny()]
        return [IsVendorOrReadOnly()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def by_category(self, request):
        """Filter products by category slug."""
        slug = request.query_params.get('slug')
        if not slug:
            return Response({"error": "slug parameter is required."}, status=400)
        products = self.get_queryset().filter(category__slug=slug)
        serializer = ProductSerializer(products, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'], permission_classes=[permissions.AllowAny])
    def reviews(self, request, pk=None):
        """Get all reviews for a product."""
        product = self.get_object()
        reviews = product.reviews.all()
        serializer = ReviewSerializer(reviews, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def add_review(self, request, pk=None):
        """Add a review for a product."""
        product = self.get_object()

        # Check if user already reviewed this product
        if Review.objects.filter(product=product, customer=request.user).exists():
            return Response(
                {"error": "You have already reviewed this product."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(product=product, customer=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], permission_classes=[permissions.IsAuthenticated])
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