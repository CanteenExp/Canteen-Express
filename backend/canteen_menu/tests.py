import json
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import CustomUser
from customer_portal.models import Order, OrderItem

class ProcessBarcodeAPITestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = CustomUser.objects.create_user(
            username="pos_staff", password="testpass", role="STAFF"
        )
        self.client.login(username="pos_staff", password="testpass")
        self.order = Order.objects.create(
            order_number="#CE-8888",
            total_amount=65.00,
            status="unpaid"
        )
        OrderItem.objects.create(
            order=self.order,
            item_name="Porksilong with Egg",
            price=50.00,
            quantity=1
        )
        OrderItem.objects.create(
            order=self.order,
            item_name="Tinapay",
            price=15.00,
            quantity=1
        )
        self.url = reverse("canteen_menu:process_barcode_api")

    def test_fetch_order_details(self):
        response = self.client.post(
            self.url,
            data=json.dumps({"action": "fetch", "order_id": "CE-8888"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["order"]["orderNumber"], "#CE-8888")
        self.assertEqual(data["order"]["total"], 65.00)
        self.assertEqual(len(data["order"]["items"]), 2)

    def test_confirm_payment(self):
        response = self.client.post(
            self.url,
            data=json.dumps({"action": "confirm_payment", "order_id": "#CE-8888"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "pending")

    def test_confirm_payment_already_paid_reissues_receipt(self):
        # The counter scanned and paid this slip once already.
        self.order.status = "pending"
        self.order.save()
        # Scanning and confirming it again must NOT warn "no longer payable":
        # the customer already cleared payment, so the cashier simply gets the
        # e-receipt re-issued and the order is untouched.
        response = self.client.post(
            self.url,
            data=json.dumps({"action": "confirm_payment", "order_id": "#CE-8888"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(data.get("already_paid"))
        self.assertNotIn("no longer payable", data.get("message", ""))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "pending")

    def test_confirm_payment_cancelled_slip_rejected(self):
        self.order.status = "cancelled"
        self.order.save()
        response = self.client.post(
            self.url,
            data=json.dumps({"action": "confirm_payment", "order_id": "#CE-8888"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertIn("cancelled", data["message"])
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "cancelled")

    def test_order_not_found(self):
        response = self.client.post(
            self.url,
            data=json.dumps({"action": "fetch", "order_id": "CE-0000"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["status"], "error")

