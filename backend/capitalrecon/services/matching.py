from decimal import Decimal

from django.db.models import F

from capitalrecon.models import LineItem, Match, Transaction

from .normalization import (
    name_found_in,
    normalize_name,
    normalize_reference,
)


def _eligible_line_items(transaction: Transaction):
    return list(
        LineItem.objects.filter(
            organization=transaction.organization,
            amount_called__gt=F("amount_funded"),
            capital_call__call_date__lte=transaction.date,
        )
        .select_related("capital_call")
        .order_by("id")
    )


def _ref_matches(transaction: Transaction, eligible):
    """Return eligible line items whose normalised reference appears in the
    normalised description or bank reference."""
    desc_norm = normalize_reference(transaction.description)
    bank_norm = normalize_reference(transaction.bank_reference)
    found = []
    for li in eligible:
        ref_norm = normalize_reference(li.reference)
        if not ref_norm:
            continue
        if ref_norm in desc_norm or ref_norm in bank_norm:
            found.append(li)
    return found


def _name_amount_matches(transaction: Transaction, eligible, amount: Decimal):
    found = []
    for li in eligible:
        if amount != li.remaining:
            continue
        name_norm = normalize_name(li.investor_entity)
        if name_found_in(name_norm, transaction.description):
            found.append(li)
    return found


def match_transaction(transaction: Transaction):
    """Run the matching rules for a credit transaction. Creates proposed
    matches (if any) and sets the transaction status / needs_review reason.
    Does not save the transaction — caller saves it."""
    amount = transaction.amount
    eligible = _eligible_line_items(transaction)

    # Step 2: reference check
    ref_hits = _ref_matches(transaction, eligible)
    if ref_hits:
        if len(ref_hits) == 1:
            li = ref_hits[0]
            if amount <= li.remaining:
                reason = (
                    f"Reference {li.reference} found; amount equals remaining "
                    f"{li.remaining:,.2f}" if amount == li.remaining
                    else f"Reference {li.reference} found; partial payment "
                    f"{amount:,.2f} of remaining {li.remaining:,.2f}"
                )
                Match.objects.create(
                    transaction=transaction,
                    line_item=li,
                    status=Match.STATUS_PROPOSED,
                    reason=reason,
                )
                transaction.status = Transaction.STATUS_SUGGESTED
                transaction.needs_review_reason = ""
                return
            else:
                # overpayment -> needs_review, no match
                transaction.status = Transaction.STATUS_NEEDS_REVIEW
                transaction.needs_review_reason = (
                    f"Reference {li.reference} found but amount {amount:,.2f} "
                    f"exceeds remaining {li.remaining:,.2f} (overpayment)."
                )
                return
        else:
            # multiple reference hits -> propose all, needs_review
            for li in ref_hits:
                Match.objects.create(
                    transaction=transaction,
                    line_item=li,
                    status=Match.STATUS_PROPOSED,
                    reason=f"Reference {li.reference} found in transaction.",
                )
            transaction.status = Transaction.STATUS_NEEDS_REVIEW
            transaction.needs_review_reason = (
                f"Multiple reference matches found ({len(ref_hits)})."
            )
            return

    # Step 3: name + amount check
    name_hits = _name_amount_matches(transaction, eligible, amount)
    if name_hits:
        if len(name_hits) == 1:
            li = name_hits[0]
            reason = (
                f"Name {li.investor_entity} found and amount equals "
                f"remaining {li.remaining:,.2f}."
            )
            Match.objects.create(
                transaction=transaction,
                line_item=li,
                status=Match.STATUS_PROPOSED,
                reason=reason,
            )
            transaction.status = Transaction.STATUS_SUGGESTED
            transaction.needs_review_reason = ""
            return
        else:
            for li in name_hits:
                Match.objects.create(
                    transaction=transaction,
                    line_item=li,
                    status=Match.STATUS_PROPOSED,
                    reason=(
                        f"Name {li.investor_entity} found and amount equals "
                        f"remaining {li.remaining:,.2f}."
                    ),
                )
            transaction.status = Transaction.STATUS_NEEDS_REVIEW
            transaction.needs_review_reason = (
                f"Multiple name+amount matches found ({len(name_hits)})."
            )
            return

    # No matches
    transaction.status = Transaction.STATUS_NEEDS_REVIEW
    transaction.needs_review_reason = "No matching reference, name or amount found."
