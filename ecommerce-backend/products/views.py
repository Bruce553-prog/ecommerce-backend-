from django.conf import settings
from rest_framework import viewsets, permissions, filters
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Category, Product
from .filters import ProductFilter
from users.permissions import IsAdminOrReadOnly, IsVendorOrReadOnly
from .serializers import (
    CategorySerializer,
    ProductSerializer,
    ProductWriteSerializer
)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]


class ProductViewSet(viewsets.ModelViewSet):
    filterset_class = ProductFilter
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description', 'category__name','tags']
    ordering_fields = ['price', 'created_at']
    parser_classes = [MultiPartParser, FormParser]
    

    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_vendor:
            if self.action in ['update', 'partial_update', 'destroy']:
                return Product.objects.filter(
                    is_active=True,
                    created_by=self.request.user
                ).select_related('category').prefetch_related('images')
        return Product.objects.filter(
            is_active=True
        ).select_related('category').prefetch_related('images')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ProductWriteSerializer
        return ProductSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'by_category']:
            return [permissions.AllowAny()]
        return [IsVendorOrReadOnly()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def by_category(self, request):
        """Filter products by category slug. /api/products/by_category/?slug=electronics"""
        slug = request.query_params.get('slug')
        if not slug:
            return Response({"error": "slug parameter is required."}, status=400)
        products = self.get_queryset().filter(category__slug=slug)
        serializer = ProductSerializer(products, many=True, context={'request': request})
        return Response(serializer.data)