from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from capitalrecon.models import Match, Organization, Transaction


class MatchingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        cls.org = Organization.objects.get(slug="northwind")

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_X_ORGANIZATION="northwind")

    def _upload(self, csv_text):
        f = SimpleUploadedFile("statement.csv", csv_text.encode("utf-8"), content_type="text/csv")
        return self.client.post(
            "/api/import/",
            {"file": f},
            format="multipart",
        )

    def test_reference_match_cc1001(self):
        csv = (
            "date,description,amount,type,reference\n"
            "2026-04-04,ACH CREDIT HALLER CAPITAL LLC CC-1001,20000.00,credit,R1\n"
        )
        resp = self._upload(csv)
        self.assertEqual(resp.status_code, 201)
        txn = Transaction.objects.get(bank_reference="R1")
        self.assertEqual(txn.status, Transaction.STATUS_SUGGESTED)
        match = txn.matches.get(status=Match.STATUS_PROPOSED)
        self.assertEqual(match.line_item.reference, "CC-1001")

    def test_reference_match_case_insensitive_partial_payment(self):
        csv = (
            "date,description,amount,type,reference\n"
            "2026-04-14,ACH CREDIT HALLER CAPITAL cc1001,7500.00,CREDIT,R2\n"
        )
        resp = self._upload(csv)
        self.assertEqual(resp.status_code, 201)
        txn = Transaction.objects.get(bank_reference="R2")
        self.assertEqual(txn.status, Transaction.STATUS_SUGGESTED)
        match = txn.matches.get(status=Match.STATUS_PROPOSED)
        self.assertEqual(match.line_item.reference, "CC-1001")

    def test_name_and_amount_match(self):
        csv = (
            "date,description,amount,type,reference\n"
            "2026-04-07,WIRE INCOMING PATEL FAMILY TRUST,12500.00,credit,N1\n"
        )
        resp = self._upload(csv)
        self.assertEqual(resp.status_code, 201)
        txn = Transaction.objects.get(bank_reference="N1")
        self.assertEqual(txn.status, Transaction.STATUS_SUGGESTED)
        match = txn.matches.get(status=Match.STATUS_PROPOSED)
        self.assertEqual(match.line_item.reference, "CC-1003")

    def test_overpayment_becomes_needs_review_no_match(self):
        csv = (
            "date,description,amount,type,reference\n"
            "2026-04-15,WIRE INCOMING PATEL FAMILY TRUST CC-1003,13000.00,credit,O1\n"
        )
        resp = self._upload(csv)
        self.assertEqual(resp.status_code, 201)
        txn = Transaction.objects.get(bank_reference="O1")
        self.assertEqual(txn.status, Transaction.STATUS_NEEDS_REVIEW)
        self.assertFalse(txn.matches.filter(status=Match.STATUS_PROPOSED).exists())

    def test_multiple_name_amount_candidates_needs_review(self):
        # To trigger multiple candidates by name+amount, we need two line items
        # with the same remaining amount and same investor name found.
        # Oakridge has CC-1005 (15000) and CC-1006 (15000).
        # Both have remaining 15000 and investor "Oakridge Holdings LLC".
        csv = (
            "date,description,amount,type,reference\n"
            "2026-04-11,WIRE INCOMING OAKRIDGE HOLDINGS LLC,15000.00,credit,M1\n"
        )
        resp = self._upload(csv)
        self.assertEqual(resp.status_code, 201)
        txn = Transaction.objects.get(bank_reference="M1")
        self.assertEqual(txn.status, Transaction.STATUS_NEEDS_REVIEW)
        proposed = txn.matches.filter(status=Match.STATUS_PROPOSED)
        self.assertEqual(proposed.count(), 2)
