from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from capitalrecon.models import LineItem, Match, Organization, Transaction


class ActionTests(TestCase):
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

    def _suggested_transaction(self):
        csv = (
            "date,description,amount,type,reference\n"
            "2026-04-03,WIRE INCOMING RAHUL SHAH TRUST REF CC-1002,25000.00,credit,ACT1\n"
        )
        self._upload(csv)
        return Transaction.objects.get(bank_reference="ACT1")

    def test_approve_updates_funded_amount(self):
        txn = self._suggested_transaction()
        li = LineItem.objects.get(reference="CC-1002")
        match = txn.matches.get(status=Match.STATUS_PROPOSED)
        resp = self.client.post(f"/api/matches/{match.id}/approve/")
        self.assertEqual(resp.status_code, 200, resp.data)
        li.refresh_from_db()
        self.assertEqual(li.amount_funded, 25000)
        self.assertEqual(li.status, LineItem.STATUS_FUNDED)
        txn.refresh_from_db()
        self.assertEqual(txn.status, Transaction.STATUS_RECONCILED)

    def test_second_approval_returns_409_no_double_funding(self):
        txn = self._suggested_transaction()
        li = LineItem.objects.get(reference="CC-1002")
        match = txn.matches.get(status=Match.STATUS_PROPOSED)
        self.client.post(f"/api/matches/{match.id}/approve/")
        li.refresh_from_db()
        self.assertEqual(li.amount_funded, 25000)
        # Second approval must fail and not double-fund
        resp = self.client.post(f"/api/matches/{match.id}/approve/")
        self.assertEqual(resp.status_code, 409)
        li.refresh_from_db()
        self.assertEqual(li.amount_funded, 25000)

    def test_reject_removes_suggestion(self):
        txn = self._suggested_transaction()
        match = txn.matches.get(status=Match.STATUS_PROPOSED)
        resp = self.client.post(f"/api/matches/{match.id}/reject/")
        self.assertEqual(resp.status_code, 200)
        txn.refresh_from_db()
        self.assertEqual(txn.status, Transaction.STATUS_NEEDS_REVIEW)

    def test_ignore_suggested_transaction(self):
        txn = self._suggested_transaction()
        resp = self.client.post(f"/api/transactions/{txn.id}/ignore/")
        self.assertEqual(resp.status_code, 200)
        txn.refresh_from_db()
        self.assertEqual(txn.status, Transaction.STATUS_IGNORED)
        self.assertFalse(txn.matches.filter(status=Match.STATUS_PROPOSED).exists())

    def test_ignore_reconciled_returns_409(self):
        txn = self._suggested_transaction()
        match = txn.matches.get(status=Match.STATUS_PROPOSED)
        self.client.post(f"/api/matches/{match.id}/approve/")
        resp = self.client.post(f"/api/transactions/{txn.id}/ignore/")
        self.assertEqual(resp.status_code, 409)
