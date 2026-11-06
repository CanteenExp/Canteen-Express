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
        self.assertEqual(self.order.status, "ready")

    def test_confirm_payment_already_paid_reissues_receipt(self):
        # The counter scanned and paid this slip once already.
        self.order.status = "ready"
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
        self.assertEqual(self.order.status, "ready")

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


class TransactionLogTabTests(TestCase):
    """The staff Transaction Logs tab lists collected money, nothing else."""

    def setUp(self):
        self.client = Client()
        self.staff = CustomUser.objects.create_user(
            username="tx_staff", password="testpass", role="STAFF"
        )
        self.client.login(username="tx_staff", password="testpass")

        self.faculty = CustomUser.objects.create_user(
            username="tx_prof", password="testpass", role="FACULTY",
            first_name="Ana", last_name="Cruz",
            email="ana@psu.palawan.edu.ph", phone="09170000001",
        )
        self.rider = CustomUser.objects.create_user(
            username="tx_rider", password="testpass", role="DELIVERY",
            first_name="Rico", last_name="Bautista",
        )

        # Walk-in pickup, paid at the counter (counter moves unpaid -> ready).
        self.walkin = Order.objects.create(
            order_number="#CE-9101", total_amount=100.00, status="ready",
            guest_name="Maria Santos", guest_phone="09171112222",
        )
        OrderItem.objects.create(
            order=self.walkin, item_name="Pancit Bihon", price=50.00, quantity=2
        )

        # Faculty delivery order, paid on handoff.
        self.delivery = Order.objects.create(
            order_number="#CE-9102", total_amount=200.00, delivery_fee=15.00,
            status="completed", customer=self.faculty,
        )
        OrderItem.objects.create(
            order=self.delivery, item_name="Chicken Adobo", price=200.00, quantity=1
        )
        DeliveryRequest.objects.create(
            order=self.delivery, rider=self.rider,
            delivery_location="Library - Room 12",
            status=DeliveryRequest.RequestStatus.DELIVERED,
        )

        # Student account, completed counter pickup.
        self.student = CustomUser.objects.create_user(
            username="tx_student", password="testpass", role="STUDENT",
            first_name="Jose", last_name="Reyes",
        )
        self.student_order = Order.objects.create(
            order_number="#CE-9103", total_amount=150.00, status="completed",
            customer=self.student,
        )

        # Not successful: unpaid slip, cancelled order, delivery still on the road.
        self.unpaid = Order.objects.create(
            order_number="#CE-9104", total_amount=80.00, status="unpaid"
        )
        Order.objects.create(
            order_number="#CE-9105", total_amount=90.00, status="cancelled"
        )
        self.in_transit = Order.objects.create(
            order_number="#CE-9106", total_amount=60.00, status="preparing",
            customer=self.student,
        )
        DeliveryRequest.objects.create(
            order=self.in_transit, delivery_location="Gym",
            status=DeliveryRequest.RequestStatus.SEARCHING,
        )

        # Prime the staff session token, then use the hashed dashboard URL.
        self.client.get(reverse("canteen_menu:staff_dashboard"))
        self.url = reverse(
            "canteen_menu:staff_dashboard_hashed",
            kwargs={"token": self.client.session["staff_secure_token"]},
        )

    def test_only_collected_transactions_are_listed(self):
        response = self.client.get(self.url + "?tab=transactions")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["tx_total"], 3)

        # Assert on the queryset: unpaid/cancelled/in-transit orders can still
        # appear elsewhere on the dashboard (e.g. the active orders queue).
        listed = {order.pk for order in response.context["tx_page_obj"]}
        self.assertEqual(listed, {self.walkin.pk, self.delivery.pk, self.student_order.pk})

        html = response.content.decode()
        self.assertIn("#CE-9101", html)
        self.assertIn("#CE-9102", html)
        self.assertIn("#CE-9103", html)

    def test_sidebar_nav_exposes_the_tab(self):
        html = self.client.get(self.url + "?tab=transactions").content.decode()
        self.assertIn("Transaction Logs", html)
        self.assertIn("activeTab = 'transactions'", html)
        # The nav entries switch in place; no reload, no missing function.
        self.assertNotIn("loadTransactionLog", html)

    def test_each_row_owns_its_expandable_detail(self):
        # The detail row is a sibling of the summary row, so the Alpine scope
        # must live on the <tbody> both rows share -- otherwise the toggle
        # would never open anything.
        html = self.client.get(self.url + "?tab=transactions").content.decode()
        self.assertEqual(html.count('<tbody x-data="{ open: false }"'), 3)
        self.assertEqual(html.count('x-show="open"'), 3)

    def test_expanded_detail_carries_items_and_contact(self):
        html = self.client.get(self.url + "?tab=transactions").content.decode()
        self.assertIn("Items purchased", html)
        self.assertIn("Pancit Bihon", html)
        self.assertIn("09171112222", html)
        self.assertIn("Chicken Adobo", html)
        self.assertIn("Library - Room 12", html)
        self.assertIn("Rico Bautista", html)

    def test_group_filters_split_the_three_audiences(self):
        # "Students & walk-ins" is one audience: the walk-in guest and the
        # account-holding student both belong to it.
        student = self.client.get(self.url + "?tab=transactions&tx_group=student").context
        self.assertEqual(student["tx_total"], 2)
        self.assertEqual(
            {order.pk for order in student["tx_page_obj"]},
            {self.walkin.pk, self.student_order.pk},
        )

        delivery = self.client.get(self.url + "?tab=transactions&tx_group=delivery").context
        self.assertEqual(delivery["tx_total"], 1)
        self.assertEqual(delivery["tx_page_obj"][0].pk, self.delivery.pk)

        faculty = self.client.get(self.url + "?tab=transactions&tx_group=faculty").context
        self.assertEqual(faculty["tx_total"], 1)
        self.assertEqual(faculty["tx_page_obj"][0].pk, self.delivery.pk)

    def test_summary_totals_match_the_filtered_rows(self):
        ctx = self.client.get(self.url + "?tab=transactions").context
        self.assertEqual(ctx["tx_summary"]["count"], 3)
        self.assertAlmostEqual(ctx["tx_summary"]["subtotal"], 450.00)
        self.assertAlmostEqual(ctx["tx_summary"]["fees"], 15.00)
        self.assertAlmostEqual(ctx["tx_summary"]["collected"], 465.00)

    def test_search_matches_guest_rider_and_room(self):
        by_guest = self.client.get(self.url + "?tab=transactions&tx_q=Maria").context
        self.assertEqual(by_guest["tx_total"], 1)
        self.assertEqual(by_guest["tx_page_obj"][0].pk, self.walkin.pk)

        by_rider = self.client.get(self.url + "?tab=transactions&tx_q=Rico").context
        self.assertEqual(by_rider["tx_total"], 1)
        self.assertEqual(by_rider["tx_page_obj"][0].pk, self.delivery.pk)

        by_room = self.client.get(self.url + "?tab=transactions&tx_q=Library").context
        self.assertEqual(by_room["tx_total"], 1)
        self.assertEqual(by_room["tx_page_obj"][0].pk, self.delivery.pk)

    def test_empty_result_renders_the_empty_state(self):
        response = self.client.get(self.url + "?tab=transactions&tx_q=nobody-matches-this")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["tx_total"], 0)
        self.assertIn("No successful transactions yet", response.content.decode())

    def test_bad_filter_values_fall_back_instead_of_500(self):
        response = self.client.get(
            self.url + "?tab=transactions&tx_group=bogus&tx_days=9999&tx_page=abc"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["tx_group"], "all")
        self.assertEqual(response.context["tx_days"], "all")

    def test_csv_export_respects_filters_and_includes_full_detail(self):
        response = self.client.get(
            reverse("canteen_menu:transaction_log_export") + "?tx_group=delivery"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("attachment;", response["Content-Disposition"])

        body = response.content.decode("utf-8-sig")
        lines = [line for line in body.splitlines() if line.strip()]
        self.assertIn("#CE-9102", body)
        self.assertNotIn("#CE-9101", body)
        self.assertIn("Rico Bautista", body)
        self.assertIn("Chicken Adobo", body)
        self.assertEqual(len(lines), 2)  # header + one delivery transaction

    def test_ledger_fragment_is_served_on_its_own(self):
        response = self.client.get(
            reverse("canteen_menu:transaction_log_ledger") + "?tx_group=delivery"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["tx_total"], 1)

        html = response.content.decode()
        self.assertTrue(html.lstrip().startswith('<div id="tx-ledger"'))
        self.assertNotIn("<!DOCTYPE html>", html)   # not the whole dashboard
        self.assertIn("#CE-9102", html)
        self.assertNotIn("#CE-9101", html)
        self.assertIn("no-cache", response["Cache-Control"])

    def test_ledger_links_are_wired_for_in_place_filtering(self):
        html = self.client.get(self.url + "?tab=transactions").content.decode()
        self.assertIn('id="tx-ledger"', html)
        self.assertIn("data-tx-nav", html)
        self.assertIn("data-tx-ledger-url", html)
        self.assertIn("js/tx-ledger.js", html)

        fragment = self.client.get(reverse("canteen_menu:transaction_log_ledger")).content.decode()
        # Four customer-group tabs, each warmed as soon as the tab opens.
        self.assertEqual(fragment.count("data-tx-prefetch"), 4)

    def test_panels_do_not_flash_the_overview_tab(self):
        import re

        def panel(html, tab):
            if tab == "transactions":
                match = re.search(r'<div id="tx-panel".*?>', html, re.S)
            else:
                match = re.search(r'<div x-show="activeTab === \'%s\'"[^>]*>' % tab, html)
            self.assertIsNotNone(match, "panel for %r not found" % tab)
            return match.group(0)

        # Reloading the ledger must paint the ledger, not the overview.
        ledger_html = self.client.get(self.url + "?tab=transactions").content.decode()
        self.assertIn("display: none", panel(ledger_html, "overview"))
        self.assertNotIn("display: none", panel(ledger_html, "transactions"))

        # A plain dashboard load still shows the overview immediately.
        plain_html = self.client.get(self.url).content.decode()
        self.assertNotIn("display: none", panel(plain_html, "overview"))
        self.assertIn("display: none", panel(plain_html, "transactions"))

    def test_non_staff_cannot_read_the_ledger(self):
        self.client.logout()
        CustomUser.objects.create_user(
            username="tx_guest", password="testpass", role="STUDENT"
        )
        self.client.login(username="tx_guest", password="testpass")

        dashboard = self.client.get(self.url + "?tab=transactions")
        self.assertEqual(dashboard.status_code, 302)
        self.assertIn(reverse("accounts:access_denied"), dashboard["Location"])

        export = self.client.get(reverse("canteen_menu:transaction_log_export"))
        self.assertEqual(export.status_code, 302)

        fragment = self.client.get(reverse("canteen_menu:transaction_log_ledger"))
        self.assertEqual(fragment.status_code, 302)
