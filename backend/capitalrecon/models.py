from django.db import models


class Organization(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=200)

    class Meta:
        ordering = ["slug"]

    def __str__(self):
        return self.name


class CapitalCall(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="capital_calls"
    )
    call_date = models.DateField()
    due_date = models.DateField()
    call_number = models.IntegerField(default=1)

    class Meta:
        ordering = ["call_date"]

    def __str__(self):
        return f"CC #{self.call_number} ({self.organization.slug})"


class LineItem(models.Model):
    STATUS_OPEN = "open"
    STATUS_PARTIALLY_FUNDED = "partially_funded"
    STATUS_FUNDED = "funded"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_PARTIALLY_FUNDED, "Partially funded"),
        (STATUS_FUNDED, "Funded"),
    ]

    capital_call = models.ForeignKey(
        CapitalCall, on_delete=models.CASCADE, related_name="line_items"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="line_items"
    )
    investor_entity = models.CharField(max_length=300)
    reference = models.CharField(max_length=100)
    amount_called = models.DecimalField(max_digits=14, decimal_places=2)
    amount_funded = models.DecimalField(max_digits=14, decimal_places=2, default="0.00")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)

    class Meta:
        ordering = ["capital_call__call_date", "reference"]

    def __str__(self):
        return f"{self.investor_entity} ({self.reference})"

    @property
    def remaining(self):
        return self.amount_called - self.amount_funded

    def refresh_status(self):
        if self.amount_funded <= 0:
            self.status = self.STATUS_OPEN
        elif self.amount_funded >= self.amount_called:
            self.status = self.STATUS_FUNDED
        else:
            self.status = self.STATUS_PARTIALLY_FUNDED


class Transaction(models.Model):
    STATUS_SUGGESTED = "suggested"
    STATUS_NEEDS_REVIEW = "needs_review"
    STATUS_RECONCILED = "reconciled"
    STATUS_IGNORED = "ignored"
    STATUS_CHOICES = [
        (STATUS_SUGGESTED, "Suggested"),
        (STATUS_NEEDS_REVIEW, "Needs review"),
        (STATUS_RECONCILED, "Reconciled"),
        (STATUS_IGNORED, "Ignored"),
    ]

    TYPE_CREDIT = "credit"
    TYPE_DEBIT = "debit"
    TYPE_CHOICES = [
        (TYPE_CREDIT, "Credit"),
        (TYPE_DEBIT, "Debit"),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="transactions"
    )
    date = models.DateField()
    description = models.TextField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    bank_reference = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SUGGESTED)
    needs_review_reason = models.TextField(blank=True, default="")

    # Airtable (optional)
    airtable_record_id = models.CharField(max_length=200, blank=True, default="")
    airtable_sync_status = models.CharField(max_length=20, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "bank_reference"],
                name="unique_bank_ref_per_org",
            ),
        ]

    def __str__(self):
        return f"{self.bank_reference} ({self.amount})"


class Match(models.Model):
    STATUS_PROPOSED = "proposed"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PROPOSED, "Proposed"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name="matches"
    )
    line_item = models.ForeignKey(
        LineItem, on_delete=models.CASCADE, related_name="matches"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PROPOSED)
    reason = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.transaction} -> {self.line_item} ({self.status})"
