from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ImportView,
    LineItemViewSet,
    MatchViewSet,
    OrganizationView,
    TransactionViewSet,
)

router = DefaultRouter()
router.register(r"transactions", TransactionViewSet, basename="transaction")
router.register(r"line-items", LineItemViewSet, basename="lineitem")
router.register(r"matches", MatchViewSet, basename="match")

urlpatterns = [
    path("organizations/", OrganizationView.as_view(), name="organizations"),
    path("import/", ImportView.as_view(), name="import"),
    path("", include(router.urls)),
]
