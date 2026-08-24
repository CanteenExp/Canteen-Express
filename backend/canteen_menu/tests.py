import json
from django.test import TestCase, Client
from django.urls import reverse
from customer_portal.models import Order, OrderItem

class ProcessBarcodeAPITestCase(TestCase):
    def setUp(self):
        self.client = Client()
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

    def test_order_not_found(self):
        response = self.client.post(
            self.url,
            data=json.dumps({"action": "fetch", "order_id": "CE-0000"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["status"], "error")

