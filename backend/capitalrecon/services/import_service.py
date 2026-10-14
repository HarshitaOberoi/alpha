import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.db import transaction

from capitalrecon.models import Match, Organization, Transaction

from .matching import match_transaction

REQUIRED_COLUMNS = ["date", "description", "amount", "type", "reference"]


class ImportError:
    def __init__(self, line, message):
        self.line = line
        self.message = message


class ImportResult:
    def __init__(self):
        self.imported = 0
        self.duplicates = 0
        self.errors = []  # list of {line, message}

    def to_dict(self):
        return {
            "imported": self.imported,
            "duplicates": self.duplicates,
            "errors": [{"line": e["line"], "message": e["message"]} for e in self.errors],
        }


def parse_amount(raw):
    """Parse a decimal amount, stripping thousands separators. Returns Decimal."""
    cleaned = raw.replace(",", "").strip()
    return Decimal(cleaned)


def parse_date(raw):
    return datetime.strptime(raw.strip(), "%Y-%m-%d").date()


def import_csv(organization: Organization, file_bytes: bytes) -> ImportResult:
    text = file_bytes.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))

    try:
        header = next(reader)
    except StopIteration:
        raise ValueError("CSV file is empty.")

    header_norm = [h.strip().lower() for h in header]
    missing = [c for c in REQUIRED_COLUMNS if c not in header_norm]
    if missing:
        raise ValueError(f"Missing column(s): {', '.join(missing)}")

    col_index = {c: header_norm.index(c) for c in REQUIRED_COLUMNS}

    result = ImportResult()
    seen_refs = set()

    # Read all rows first so valid rows are still imported even if some fail.
    # We process row-by-row; each row is independent.
    line_number = 1  # header is line 1
    with transaction.atomic():
        for row in reader:
            line_number += 1
            if not row or all(cell.strip() == "" for cell in row):
                continue

            # Ensure row has enough columns
            if len(row) <= max(col_index.values()):
                result.errors.append({"line": line_number, "message": "Row has too few columns."})
                continue

            raw_date = row[col_index["date"]].strip()
            description = row[col_index["description"]].strip()
            raw_amount = row[col_index["amount"]].strip()
            raw_type = row[col_index["type"]].strip().lower()
            reference = row[col_index["reference"]].strip()

            # Validate description
            if not description:
                result.errors.append({"line": line_number, "message": "Description is required."})
                continue

            # Validate reference
            if not reference:
                result.errors.append({"line": line_number, "message": "Reference is required."})
                continue

            # Validate type
            if raw_type not in ("credit", "debit"):
                result.errors.append(
                    {"line": line_number, "message": f"Invalid type '{raw_type}'. Must be credit or debit."}
                )
                continue

            # Validate date
            try:
                txn_date = parse_date(raw_date)
            except (ValueError, TypeError):
                result.errors.append(
                    {"line": line_number, "message": f"Invalid date '{raw_date}'. Use YYYY-MM-DD."}
                )
                continue

            # Validate amount
            try:
                amount = parse_amount(raw_amount)
            except (InvalidOperation, ValueError):
                result.errors.append(
                    {"line": line_number, "message": f"Invalid amount '{raw_amount}'."}
                )
                continue

            if amount == 0:
                result.errors.append({"line": line_number, "message": "Amount cannot be zero."})
                continue

            if raw_type == "credit" and amount <= 0:
                result.errors.append(
                    {"line": line_number, "message": "Credit amount must be positive."}
                )
                continue
            if raw_type == "debit" and amount >= 0:
                result.errors.append(
                    {"line": line_number, "message": "Debit amount must be negative."}
                )
                continue

            # Duplicate check: same org + bank_reference (already imported or in this file)
            if reference in seen_refs:
                result.duplicates += 1
                result.errors.append(
                    {"line": line_number, "message": f"Duplicate reference '{reference}' in this file."}
                )
                continue
            if Transaction.objects.filter(organization=organization, bank_reference=reference).exists():
                result.duplicates += 1
                result.errors.append(
                    {"line": line_number, "message": f"Duplicate reference '{reference}' already imported."}
                )
                continue

            seen_refs.add(reference)

            # Create transaction
            txn = Transaction(
                organization=organization,
                date=txn_date,
                description=description,
                amount=amount,
                type=raw_type,
                bank_reference=reference,
            )

            if raw_type == "debit":
                txn.status = Transaction.STATUS_IGNORED
                txn.save()
            else:
                # credit: save first, then match
                txn.save()
                match_transaction(txn)
                txn.save()

            result.imported += 1

    return result
