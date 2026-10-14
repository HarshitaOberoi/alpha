from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from capitalrecon.models import LineItem, Organization, Transaction


class ImportTests(TestCase):
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

    def test_missing_column_rejects_and_saves_nothing(self):
        before = Transaction.objects.count()
        csv = "date,description,amount,reference\n2026-04-03,WIRE,100.00,REF1\n"
        resp = self._upload(csv)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("type", resp.data["error"])
        self.assertEqual(Transaction.objects.count(), before)

    def test_thousands_separator_parsed_as_decimal(self):
        csv = (
            "date,description,amount,type,reference\n"
            '2026-04-03,WIRE INCOMING HALLER CAPITAL CC-1001,"27,500.00",credit,T1\n'
        )
        resp = self._upload(csv)
        self.assertEqual(resp.status_code, 201, resp.data)
        txn = Transaction.objects.get(bank_reference="T1")
        self.assertEqual(txn.amount, 27500)
        # Confirm it is a Decimal, not a float
        from decimal import Decimal
        self.assertIsInstance(txn.amount, Decimal)

    def test_credit_must_be_positive(self):
        csv = (
            "date,description,amount,type,reference\n"
            "2026-04-03,WIRE,-100.00,credit,T2\n"
        )
        resp = self._upload(csv)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["imported"], 0)
        self.assertFalse(Transaction.objects.filter(bank_reference="T2").exists())

    def test_debit_must_be_negative(self):
        csv = (
            "date,description,amount,type,reference\n"
            "2026-04-03,FEE,100.00,debit,T3\n"
        )
        resp = self._upload(csv)
        self.assertEqual(resp.data["imported"], 0)

    def test_invalid_date_rejected(self):
        csv = (
            "date,description,amount,type,reference\n"
            "2026-04-31,WIRE,100.00,credit,T4\n"
        )
        resp = self._upload(csv)
        self.assertEqual(resp.data["imported"], 0)
        self.assertTrue(any("Invalid date" in e["message"] for e in resp.data["errors"]))

    def test_duplicate_inside_file_skipped(self):
        csv = (
            "date,description,amount,type,reference\n"
            "2026-04-03,WIRE A,100.00,credit,DUP1\n"
            "2026-04-03,WIRE B,200.00,credit,DUP1\n"
        )
        resp = self._upload(csv)
        self.assertEqual(resp.data["imported"], 1)
        self.assertEqual(resp.data["duplicates"], 1)

    def test_duplicate_reupload_skipped(self):
        csv = (
            "date,description,amount,type,reference\n"
            "2026-04-03,WIRE A,100.00,credit,DUP2\n"
        )
        self._upload(csv)
        resp = self._upload(csv)
        self.assertEqual(resp.data["imported"], 0)
        self.assertEqual(resp.data["duplicates"], 1)

    def test_valid_rows_imported_alongside_invalid(self):
        csv = (
            "date,description,amount,type,reference\n"
            "2026-04-03,WIRE OK,100.00,credit,GOOD1\n"
            "2026-04-31,WIRE BAD,100.00,credit,BAD1\n"
        )
        resp = self._upload(csv)
        self.assertEqual(resp.data["imported"], 1)
        self.assertEqual(len(resp.data["errors"]), 1)
