from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import LineItem, Match, Organization, Transaction
from .serializers import (
    LineItemSerializer,
    MatchSerializer,
    OrganizationSerializer,
    TransactionSerializer,
)
from .services.import_service import import_csv
from .services.reconciliation import approve_match, ignore_transaction, reject_match
from config.exceptions import Conflict


class OrganizationView(APIView):
    def get(self, request):
        orgs = Organization.objects.all()
        return Response(OrganizationSerializer(orgs, many=True).data)


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TransactionSerializer

    def get_queryset(self):
        return (
            Transaction.objects.filter(organization=self.request.organization)
            .prefetch_related("matches__line_item")
            .order_by("-date", "-id")
        )

    @action(detail=True, methods=["post"])
    def ignore(self, request, pk=None):
        txn = self.get_object()
        try:
            txn = ignore_transaction(txn)
        except Conflict as e:
            return Response({"error": str(e)}, status=status.HTTP_409_CONFLICT)
        return Response(TransactionSerializer(txn).data)


class LineItemViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LineItemSerializer

    def get_queryset(self):
        return LineItem.objects.filter(organization=self.request.organization).select_related(
            "capital_call"
        )


class MatchViewSet(viewsets.GenericViewSet):
    serializer_class = MatchSerializer
    queryset = Match.objects.all()

    def get_queryset(self):
        return Match.objects.filter(
            transaction__organization=self.request.organization
        ).select_related("line_item", "transaction")

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        match = self.get_object()
        try:
            match = approve_match(match)
        except Conflict as e:
            return Response({"error": str(e)}, status=status.HTTP_409_CONFLICT)
        return Response(MatchSerializer(match).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        match = self.get_object()
        match = reject_match(match)
        return Response(MatchSerializer(match).data)


class ImportView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        if "file" not in request.FILES:
            return Response(
                {"error": "No file provided. Upload a CSV as 'file'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        uploaded = request.FILES["file"]
        content = uploaded.read()
        try:
            result = import_csv(request.organization, content)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result.to_dict(), status=status.HTTP_201_CREATED)
