from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from capitalrecon.models import Match, Organization, Transaction


class OrganizationScopingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def setUp(self):
        self.client = APIClient()

    def test_missing_header_returns_400(self):
        resp = self.client.get("/api/transactions/")
        self.assertEqual(resp.status_code, 400)

    def test_unknown_org_returns_404(self):
        resp = self.client.get("/api/transactions/", HTTP_X_ORGANIZATION="unknown")
        self.assertEqual(resp.status_code, 404)

    def _upload(self, csv_text):
        f = SimpleUploadedFile("s.csv", csv_text.encode("utf-8"), content_type="text/csv")
        return self.client.post("/api/import/", {"file": f}, format="multipart")

    def test_listing_isolated_per_org(self):
        # Import a northwind transaction
        self.client.credentials(HTTP_X_ORGANIZATION="northwind")
        csv = (
            "date,description,amount,type,reference\n"
            "2026-04-03,WIRE INCOMING RAHUL SHAH TRUST REF CC-1002,25000.00,credit,ISO1\n"
        )
        self._upload(csv)
        # Northwind sees it
        resp = self.client.get("/api/transactions/")
        self.assertEqual(resp.status_code, 200)
        refs = [t["bank_reference"] for t in resp.data]
        self.assertIn("ISO1", refs)

        # Bluebird does not see it
        self.client.credentials(HTTP_X_ORGANIZATION="bluebird")
        resp = self.client.get("/api/transactions/")
        refs = [t["bank_reference"] for t in resp.data]
        self.assertNotIn("ISO1", refs)

    def test_cross_org_approve_returns_404(self):
        self.client.credentials(HTTP_X_ORGANIZATION="northwind")
        csv = (
            "date,description,amount,type,reference\n"
            "2026-04-03,WIRE INCOMING RAHUL SHAH TRUST REF CC-1002,25000.00,credit,ISO2\n"
        )
        self._upload(csv)
        txn = Transaction.objects.get(bank_reference="ISO2")
        match = txn.matches.get(status=Match.STATUS_PROPOSED)

        # Approve as bluebird -> 404
        self.client.credentials(HTTP_X_ORGANIZATION="bluebird")
        resp = self.client.post(f"/api/matches/{match.id}/approve/")
        self.assertEqual(resp.status_code, 404)
