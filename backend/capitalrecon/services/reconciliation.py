from django.db import transaction

from capitalrecon.models import LineItem, Match, Transaction
from config.exceptions import Conflict


def approve_match(match: Match):
    """Approve a proposed match atomically.

    - Re-checks the amount against the line item's remaining -> 409 if too large.
    - Adds amount to funded, updates line item status.
    - Approves the chosen match, rejects the transaction's other matches.
    - Marks the transaction reconciled.
    - A line item is never funded twice: a duplicate approval returns 409.
    """
    with transaction.atomic():
        line_item = LineItem.objects.select_for_update().get(pk=match.line_item_id)
        # Refresh match inside the lock
        match = Match.objects.select_for_update().get(pk=match.pk)
        txn = Transaction.objects.select_for_update().get(pk=match.transaction_id)

        # Never fund twice: match must still be proposed and txn not reconciled.
        if match.status != Match.STATUS_PROPOSED:
            raise Conflict("This match has already been processed.")
        if txn.status == Transaction.STATUS_RECONCILED:
            raise Conflict("Transaction is already reconciled.")

        amount = txn.amount
        if amount > line_item.remaining:
            raise Conflict(
                f"Amount {amount:,.2f} exceeds remaining {line_item.remaining:,.2f}."
            )

        line_item.amount_funded += amount
        line_item.refresh_status()
        line_item.save()

        match.status = Match.STATUS_APPROVED
        match.save()

        # Reject other matches for this transaction
        Match.objects.filter(transaction=txn).exclude(pk=match.pk).update(
            status=Match.STATUS_REJECTED
        )

        txn.status = Transaction.STATUS_RECONCILED
        txn.needs_review_reason = ""
        txn.save()

    return match


def reject_match(match: Match):
    with transaction.atomic():
        match = Match.objects.select_for_update().get(pk=match.pk)
        if match.status != Match.STATUS_PROPOSED:
            return match
        match.status = Match.STATUS_REJECTED
        match.save()

        txn = match.transaction
        has_proposed = Match.objects.filter(
            transaction=txn, status=Match.STATUS_PROPOSED
        ).exists()
        if not has_proposed and txn.status == Transaction.STATUS_SUGGESTED:
            txn.status = Transaction.STATUS_NEEDS_REVIEW
            txn.needs_review_reason = "All proposed matches were rejected."
            txn.save()
    return match


def ignore_transaction(txn: Transaction):
    with transaction.atomic():
        txn = Transaction.objects.select_for_update().get(pk=txn.pk)
        if txn.status == Transaction.STATUS_RECONCILED:
            raise Conflict("Cannot ignore a reconciled transaction.")
        if txn.status == Transaction.STATUS_IGNORED:
            return txn

        Match.objects.filter(transaction=txn, status=Match.STATUS_PROPOSED).update(
            status=Match.STATUS_REJECTED
        )
        txn.status = Transaction.STATUS_IGNORED
        txn.needs_review_reason = ""
        txn.save()
    return txn
