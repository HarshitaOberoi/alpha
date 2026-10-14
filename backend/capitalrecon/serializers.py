from rest_framework import serializers

from .models import LineItem, Match, Organization, Transaction


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["slug", "name"]


class MatchSerializer(serializers.ModelSerializer):
    line_item_reference = serializers.CharField(source="line_item.reference", read_only=True)
    investor_entity = serializers.CharField(source="line_item.investor_entity", read_only=True)
    amount_called = serializers.DecimalField(
        source="line_item.amount_called", max_digits=14, decimal_places=2, read_only=True
    )
    remaining = serializers.DecimalField(
        source="line_item.remaining", max_digits=14, decimal_places=2, read_only=True
    )

    class Meta:
        model = Match
        fields = [
            "id",
            "line_item",
            "line_item_reference",
            "investor_entity",
            "amount_called",
            "remaining",
            "status",
            "reason",
        ]


class TransactionSerializer(serializers.ModelSerializer):
    matches = MatchSerializer(many=True, read_only=True)
    suggested_investor = serializers.SerializerMethodField()
    suggested_reference = serializers.SerializerMethodField()
    suggested_reason = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            "id",
            "date",
            "description",
            "amount",
            "type",
            "bank_reference",
            "status",
            "needs_review_reason",
            "matches",
            "suggested_investor",
            "suggested_reference",
            "suggested_reason",
        ]

    def _proposed_match(self, obj):
        for m in obj.matches.all():
            if m.status == Match.STATUS_PROPOSED:
                return m
        return None

    def get_suggested_investor(self, obj):
        m = self._proposed_match(obj)
        return m.line_item.investor_entity if m else None

    def get_suggested_reference(self, obj):
        m = self._proposed_match(obj)
        return m.line_item.reference if m else None

    def get_suggested_reason(self, obj):
        m = self._proposed_match(obj)
        if m:
            return m.reason
        if obj.status == Transaction.STATUS_NEEDS_REVIEW:
            return obj.needs_review_reason
        return ""


class LineItemSerializer(serializers.ModelSerializer):
    remaining = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    call_date = serializers.DateField(source="capital_call.call_date", read_only=True)
    due_date = serializers.DateField(source="capital_call.due_date", read_only=True)
    call_number = serializers.IntegerField(source="capital_call.call_number", read_only=True)

    class Meta:
        model = LineItem
        fields = [
            "id",
            "call_number",
            "call_date",
            "due_date",
            "investor_entity",
            "reference",
            "amount_called",
            "amount_funded",
            "remaining",
            "status",
        ]
