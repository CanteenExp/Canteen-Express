import json
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import CustomUser
from customer_portal.models import Order, OrderItem, OrderFeedback
from deliveries.models import DeliveryRequest

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

    def test_expired_session_returns_json_not_login_redirect(self):
        """The POS sends Accept: application/json so an expired session comes
        back as a clean 401 JSON. Without it role_required() 302s to the login
        page and the POS reports a bogus 'Server connection error while
        scanning barcode.'"""
        self.client.logout()
        response = self.client.post(
            self.url,
            data=json.dumps({"action": "fetch", "order_id": "1149"}),
            content_type="application/json",
            HTTP_ACCEPT="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertFalse(response.json()["success"])

    def test_pos_page_advertises_json_requests(self):
        """counter_pos.html must send the headers role_required() looks for."""
        html = self.client.get(reverse("canteen_menu:counter_pos")).content.decode()
        self.assertIn("'Accept': 'application/json'", html)
        self.assertIn("'X-Requested-With': 'XMLHttpRequest'", html)
        self.assertIn("Your session expired", html)



class FeedbackChannelSegregationTests(TestCase):
    """Kiosk and delivery reviews must be graded and listed separately."""

    def setUp(self):
        self.client = Client()
        self.staff = CustomUser.objects.create_user(
            username="fb_staff", password="testpass", role="STAFF"
        )
        self.client.login(username="fb_staff", password="testpass")

        self.kiosk_order = Order.objects.create(
            order_number="#CE-7001", total_amount=120.00, delivery_fee=0, status="completed"
        )
        OrderItem.objects.create(
            order=self.kiosk_order, item_name="Porksilong", price=60.00, quantity=1
        )
        OrderItem.objects.create(
            order=self.kiosk_order, item_name="Tinapay", price=60.00, quantity=1
        )
        OrderFeedback.objects.create(
            order=self.kiosk_order,
            customer=self.staff,
            rating=5,
            comment="Fast counter service, food was hot.",
        )

        self.rider = CustomUser.objects.create_user(
            username="fb_rider", password="testpass", role="DELIVERY", first_name="Rico"
        )
        self.delivery_order = Order.objects.create(
            order_number="#CE-7002", total_amount=150.00, delivery_fee=15.00, status="completed"
        )
        OrderItem.objects.create(
            order=self.delivery_order, item_name="Sinigang", price=150.00, quantity=1
        )
        DeliveryRequest.objects.create(
            order=self.delivery_order,
            rider=self.rider,
            delivery_location="Dorm 3 - Room 214",
            status=DeliveryRequest.RequestStatus.DELIVERED,
        )
        OrderFeedback.objects.create(
            order=self.delivery_order,
            customer=self.staff,
            rating=2,
            comment="Rider arrived late and the soup spilled.",
        )

        # The staff dashboard is token-guarded: prime the session token, then
        # request the hashed URL that matches it.
        self.client.get(reverse("canteen_menu:staff_dashboard"))
        self.url = reverse(
            "canteen_menu:staff_dashboard_hashed",
            kwargs={"token": self.client.session["staff_secure_token"]},
        )

    def test_context_splits_kiosk_and_delivery(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        self.assertEqual(len(ctx["fb_kiosk"]), 1)
        self.assertEqual(len(ctx["fb_delivery"]), 1)
        self.assertEqual(ctx["fb_total"], 2)

        self.assertEqual(ctx["fb_kiosk"][0].channel, "kiosk")
        self.assertEqual(ctx["fb_delivery"][0].channel, "delivery")

    def test_channel_stats_are_independent(self):
        ctx = self.client.get(self.url).context

        self.assertEqual(ctx["fb_kiosk_stats"]["count"], 1)
        self.assertEqual(ctx["fb_kiosk_stats"]["avg"], 5.0)
        self.assertEqual(ctx["fb_delivery_stats"]["count"], 1)
        self.assertEqual(ctx["fb_delivery_stats"]["avg"], 2.0)
        self.assertEqual(ctx["fb_kiosk_stats"]["praised"], 1)
        self.assertEqual(ctx["fb_delivery_stats"]["detractors"], 1)
        self.assertEqual(ctx["fb_overall"]["avg"], 3.5)

        # Breakdown rows are 5 -> 1 and sum to the channel total.
        stars = [b["star"] for b in ctx["fb_delivery_stats"]["breakdown"]]
        self.assertEqual(stars, [5, 4, 3, 2, 1])
        self.assertEqual(sum(b["count"] for b in ctx["fb_kiosk_stats"]["breakdown"]), 1)

    def test_review_card_fields(self):
        ctx = self.client.get(self.url).context

        delivery_fb = ctx["fb_delivery"][0]
        self.assertEqual(delivery_fb.display_name, "fb_staff")
        self.assertEqual(delivery_fb.initials, "F")
        self.assertEqual(delivery_fb.stars, [True, True, False, False, False])
        self.assertTrue(delivery_fb.has_comment)

        kiosk_fb = ctx["fb_kiosk"][0]
        self.assertEqual(kiosk_fb.stars, [True, True, True, True, True])
        # Nothing but comment + rating is decorated onto a row.
        self.assertFalse(hasattr(kiosk_fb, "destination"))
        self.assertFalse(hasattr(kiosk_fb, "rider_name"))

    def test_panel_renders_both_channels(self):
        html = self.client.get(self.url).content.decode()
        self.assertIn("Kiosk Reviews", html)
        self.assertIn("Delivery Reviews", html)
        self.assertIn("Kiosk / Counter Pick-up", html)
        # The delivery complaint must not leak into the kiosk column.
        kiosk_col = html.split("Delivery Reviews")[0]
        self.assertIn("Fast counter service", kiosk_col)
        self.assertNotIn("Rider arrived late", kiosk_col)

    def test_review_card_is_comment_and_rating_only(self):
        from django.template.loader import render_to_string
        from customer_portal.feedback_context import build_feedback_context

        fb = build_feedback_context()["fb_delivery"][0]
        card = render_to_string("partials/feedback_card.html", {"fb": fb})

        self.assertIn("fb_staff", card)
        self.assertIn("Rider arrived late and the soup spilled.", card)
        self.assertIn("fa-star", card)
        self.assertIn("2.0", card)
        # Order / rider / drop-off detail belongs to the summary, not the card.
        self.assertNotIn("Dorm 3 - Room 214", card)
        self.assertNotIn("Proof of delivery", card)
        self.assertNotIn("Delivery fee", card)
        self.assertNotIn("fa-location-dot", card)

    def test_empty_state_per_channel(self):
        OrderFeedback.objects.all().delete()
        DeliveryRequest.objects.all().delete()
        ctx = self.client.get(self.url).context
        self.assertEqual(ctx["fb_total"], 0)
        self.assertEqual(ctx["fb_kiosk_stats"]["avg"], 0.0)
        self.assertEqual(ctx["fb_delivery_stats"]["count"], 0)
        html = self.client.get(self.url).content.decode()
        self.assertIn("No kiosk reviews yet", html)
        self.assertIn("No delivery reviews yet", html)

    def test_anonymous_walkin_gets_name_and_initials(self):
        OrderFeedback.objects.create(order=None, customer=None, rating=4, comment="Walk-in guest")
        fb = self.client.get(self.url).context["fb_kiosk"][0]
        self.assertEqual(fb.display_name, "Walk-in Guest")
        self.assertEqual(fb.initials, "WG")
        self.assertIsNone(fb.order)
