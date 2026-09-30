import json
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from canteen_menu.models import Category, MenuItem
from customer_portal.models import Order
from customer_portal.views import expire_stale_unpaid_orders
from deliveries.models import DeliveryRequest

class CheckoutTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            username='faculty_test',
            password='password123',
            role='FACULTY'
        )
        self.category = Category.objects.create(name='Rice Meals')
        self.item = MenuItem.objects.create(
            category=self.category,
            name='Pork Adobo',
            price=75.00,
            stock=10
        )
        self.checkout_url = reverse('customer_portal:process_checkout')

    def test_faculty_delivery_checkout(self):
        self.client.login(username='faculty_test', password='password123')
        payload = {
            'cart': [
                {'id': self.item.id, 'name': 'Pork Adobo', 'price': 75.00, 'qty': 1}
            ],
            'total_amount': 90.00,
            'is_delivery': True,
            'delivery_location': 'Faculty Office Bldg, Room 101',
            'payment_method': 'COD',
            'dest_lat': 9.77725,
            'dest_lng': 118.73480
        }
        response = self.client.post(
            self.checkout_url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('order_number', data)
        # Server recomputes the subtotal from the cart (₱75), fee = ₱15 base.
        self.assertEqual(float(data['delivery_fee']), 15.0)
        self.assertEqual(float(data['total_payment']), 90.0)

    def test_delivery_checkout_uses_server_subtotal_not_client_total(self):
        # Client tries to sneak a smaller total_amount; server must ignore it
        # and recompute fee from the actual cart prices.
        self.client.login(username='faculty_test', password='password123')
        payload = {
            'cart': [
                {'id': self.item.id, 'name': 'Pork Adobo', 'price': 75.00, 'qty': 1},
                {'id': self.item.id, 'name': 'Pork Adobo', 'price': 75.00, 'qty': 3},
            ],
            'total_amount': 1.00,  # bogus, must be ignored
            'is_delivery': True,
            'delivery_location': 'Faculty Office Bldg, Room 101',
            'payment_method': 'COD',
            'dest_lat': 9.77725,
            'dest_lng': 118.73480
        }
        response = self.client.post(
            self.checkout_url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        from customer_portal.models import Order
        created = Order.objects.get(order_number=data['order_number'])
        # Subtotal = 75 x 4 = ₱300 -> fee stays ₱15 (exact boundary).
        self.assertEqual(float(created.total_amount), 300.0)
        self.assertEqual(float(created.delivery_fee), 15.0)
        self.assertEqual(float(data['total_payment']), 315.0)

    def test_delivery_fee_scales_per_300_php_blocks(self):
        from deliveries.utils import delivery_fee_for_order
        self.assertEqual(delivery_fee_for_order(0), 15.0)
        self.assertEqual(delivery_fee_for_order(15), 15.0)
        self.assertEqual(delivery_fee_for_order(300), 15.0)
        self.assertEqual(delivery_fee_for_order(300.01), 30.0)
        self.assertEqual(delivery_fee_for_order(600), 30.0)
        self.assertEqual(delivery_fee_for_order(601), 45.0)
        self.assertEqual(delivery_fee_for_order(900), 45.0)
        self.assertEqual(delivery_fee_for_order(901), 60.0)
        self.assertEqual(delivery_fee_for_order(1250), 75.0)

    def test_kiosk_pickup_checkout_has_no_delivery_fee(self):
        self.client.login(username='faculty_test', password='password123')
        payload = {
            'cart': [{'id': self.item.id, 'name': 'Pork Adobo', 'price': 75.00, 'qty': 2}],
            'total_amount': 150.00,
            'is_delivery': False,
        }
        response = self.client.post(
            self.checkout_url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(float(data['delivery_fee']), 0.0)
        self.assertEqual(float(data['total_payment']), 150.0)

    @override_settings(ENFORCE_GEOFENCE=True)
    def test_delivery_checkout_rejected_outside_campus(self):
        self.client.login(username='faculty_test', password='password123')
        payload = {
            'cart': [
                {'id': self.item.id, 'name': 'Pork Adobo', 'price': 75.00, 'qty': 1}
            ],
            'total_amount': 90.00,
            'is_delivery': True,
            'delivery_location': 'Somewhere in Manila',
            'payment_method': 'COD',
            'dest_lat': 14.5995,
            'dest_lng': 120.9842
        }
        response = self.client.post(
            self.checkout_url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 422)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('campus', data['message'].lower())

    @override_settings(ENFORCE_GEOFENCE=True)
    def test_delivery_checkout_rejected_missing_coords(self):
        self.client.login(username='faculty_test', password='password123')
        payload = {
            'cart': [
                {'id': self.item.id, 'name': 'Pork Adobo', 'price': 75.00, 'qty': 1}
            ],
            'total_amount': 90.00,
            'is_delivery': True,
            'delivery_location': 'Faculty Office Bldg, Room 101',
            'payment_method': 'COD'
        }
        response = self.client.post(
            self.checkout_url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 422)


class KioskSlipExpiryTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = CustomUser.objects.create_user(
            username='expiry_staff', password='testpass', role='STAFF',
        )
        self.client.login(username='expiry_staff', password='testpass')
        self.category = Category.objects.create(name='Rice Meals')
        self.item = MenuItem.objects.create(
            category=self.category, name='Pork Adobo', price=75.00, stock=10)
        self.checkout_url = reverse('customer_portal:process_checkout')

    def _place_pickup(self, qty=2):
        payload = {
            'cart': [{'id': self.item.id, 'name': 'Pork Adobo', 'price': 75.00, 'qty': qty}],
            'total_amount': 75.0 * qty,
            'is_delivery': False,
        }
        res = self.client.post(self.checkout_url, data=json.dumps(payload),
                               content_type='application/json')
        self.assertEqual(res.status_code, 200)
        return Order.objects.get(order_number=res.json()['order_number'])

    def _backdate(self, order, hours=2):
        Order.objects.filter(pk=order.pk).update(
            created_at=timezone.now() - timedelta(hours=hours))
        order.refresh_from_db()

    def test_pickup_checkout_sends_expiry_clock(self):
        order = self._place_pickup()
        self.assertEqual(order.status, 'unpaid')
        res = self.client.post(self.checkout_url, data=json.dumps({
            'cart': [{'id': self.item.id, 'name': 'Pork Adobo', 'price': 75.00, 'qty': 1}],
            'total_amount': 75.0, 'is_delivery': False,
        }), content_type='application/json')
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['expiry_hours'], 1)
        self.assertIsNotNone(data['expires_at'])

    def test_fresh_unpaid_slip_is_not_expired(self):
        order = self._place_pickup()
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock, 8)
        swept = expire_stale_unpaid_orders()
        self.assertEqual(swept, 0)
        order.refresh_from_db()
        self.assertEqual(order.status, 'unpaid')

    def test_stale_unpaid_slip_is_cancelled_and_stock_restored(self):
        order = self._place_pickup()
        self._backdate(order, hours=2)
        swept = expire_stale_unpaid_orders()
        self.assertEqual(swept, 1)
        order.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')
        # Stock released back to the menu, like a counter cancellation.
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock, 10)
        from activity_log.models import ActivityLog
        log = ActivityLog.objects.filter(target=order.order_number).first()
        self.assertIsNotNone(log)
        self.assertIn('expired', log.action.lower())

    def test_late_payment_of_expired_slip_is_rejected(self):
        order = self._place_pickup()
        self._backdate(order, hours=2)
        res = self.client.post(
            reverse('canteen_menu:process_barcode_api'),
            data=json.dumps({'action': 'confirm_payment',
                             'order_id': order.order_number}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')

    def test_kiosk_status_api_reports_expired(self):
        order = self._place_pickup()
        self._backdate(order, hours=2)
        url = reverse('customer_portal:check_order_status_api',
                      args=[order.order_number])
        res = self.client.get(url)
        data = res.json()
        self.assertTrue(data['exists'])
        self.assertEqual(data['status'], 'cancelled')
        self.assertTrue(data['expired'])
        self.assertIsNone(data['expires_at'])

    def test_paid_order_has_no_expiry_clock(self):
        order = self._place_pickup()
        order.status = 'pending'
        order.save(update_fields=['status'])
        url = reverse('customer_portal:check_order_status_api',
                      args=[order.order_number])
        data = self.client.get(url).json()
        self.assertEqual(data['status'], 'pending')
        self.assertIsNone(data['expires_at'])

class FeedbackRatingTestCase(TestCase):
    """Ratings must work for a delivered order with a proof photo.

    Regression cover for the bug where submit_feedback_api stripped the "#"
    from the slip number before looking the order up. Stored numbers keep the
    prefix ("#CE-5151"), so the lookup never matched and every rating -- from
    both the faculty portal and the kiosk history panel -- came back 400.
    """

    def setUp(self):
        self.client = Client()
        self.customer = CustomUser.objects.create_user(
            username='rate_cust', password='testpass', role='FACULTY',
        )
        self.stranger = CustomUser.objects.create_user(
            username='rate_stranger', password='testpass', role='FACULTY',
        )
        self.rider = CustomUser.objects.create_user(
            username='rate_rider', password='testpass', role='DELIVERY',
        )
        self.url = reverse('customer_portal:submit_feedback_api')

    def _order(self, number, status='completed'):
        return Order.objects.create(
            order_number=number, total_amount=120.00,
            delivery_fee=30.00, status=status, customer=self.customer,
        )

    def _delivered(self, order, with_photo=True):
        delivery = DeliveryRequest.objects.create(
            order=order, rider=self.rider,
            status=DeliveryRequest.RequestStatus.DELIVERED,
        )
        if with_photo:
            delivery.proof_photo = 'delivery_proofs/proof.png'
            delivery.save(update_fields=['proof_photo'])
        return delivery

    def _post(self, number, rating=5, user=None):
        client = Client()
        if user is not None:
            client.force_login(user)
        return client.post(self.url, data=json.dumps({
            'order_number': number, 'rating': rating, 'comment': 'Great meal',
        }), content_type='application/json')

    def test_hash_prefixed_slip_number_is_accepted(self):
        order = self._order('#CE-5151')
        self._delivered(order)
        res = self._post('#CE-5151', user=self.customer)
        self.assertEqual(res.status_code, 200, res.content)
        self.assertTrue(res.json()['success'])
        self.assertEqual(order.feedbacks.count(), 1)

    def test_prose_label_from_the_view_order_heading_is_accepted(self):
        # The faculty modal heading is "Order Details & Live Tracking (#CE-5151)";
        # the old code scraped that and sent the prose instead of the slip number.
        order = self._order('#CE-5152')
        self._delivered(order)
        res = self._post('Order Details & Live Tracking (#CE-5152)', user=self.customer)
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(order.feedbacks.count(), 1)

    def test_unknown_slip_number_is_404_not_a_false_completed_message(self):
        res = self._post('#CE-0000', user=self.customer)
        self.assertEqual(res.status_code, 404)

    def test_rating_blocked_until_rider_marks_delivered(self):
        order = self._order('#CE-5153', status='pending')
        delivery = DeliveryRequest.objects.create(
            order=order, rider=self.rider,
            status=DeliveryRequest.RequestStatus.ACCEPTED)
        delivery.proof_photo = 'delivery_proofs/proof.png'
        delivery.save(update_fields=['proof_photo'])
        res = self._post('#CE-5153', user=self.customer)
        self.assertEqual(res.status_code, 400)
        self.assertIn('delivered', res.json()['message'].lower())
        self.assertEqual(order.feedbacks.count(), 0)

    def test_rating_blocked_until_proof_photo_is_attached(self):
        order = self._order('#CE-5154')
        self._delivered(order, with_photo=False)
        res = self._post('#CE-5154', user=self.customer)
        self.assertEqual(res.status_code, 400)
        self.assertIn('photo', res.json()['message'].lower())
        self.assertEqual(order.feedbacks.count(), 0)

    def test_pickup_order_rates_on_completed_status(self):
        # No rider is involved, so the order's own status is the whole gate.
        order = self._order('#CE-5155')
        res = self._post('#CE-5155', user=self.customer)
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(order.feedbacks.count(), 1)

    def test_stranger_cannot_rate_someone_elses_order(self):
        order = self._order('#CE-5156')
        self._delivered(order)
        res = self._post('#CE-5156', user=self.stranger)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(order.feedbacks.count(), 0)

    def test_resubmitting_updates_instead_of_duplicating(self):
        order = self._order('#CE-5157')
        self._delivered(order)
        self._post('#CE-5157', rating=1, user=self.customer)
        self._post('#CE-5157', rating=5, user=self.customer)
        self.assertEqual(order.feedbacks.count(), 1)
        self.assertEqual(order.feedbacks.first().rating, 5)


class KioskStatusPollEndpointTests(TestCase):
    """The kiosk is public (no login), so its receipt auto-pop must poll the
    anonymous order-status endpoint. process_barcode_api is gated to STAFF and
    answers anonymous guests with a 302 to the staff login page, which silently
    killed the kiosk e-receipt: the slip stayed on the queue screen even after
    the POS had paid the order."""

    def setUp(self):
        self.order = Order.objects.create(
            order_number='#CE-7777', total_amount=50.00, status='unpaid'
        )

    def test_anonymous_kiosk_reads_unpaid_status(self):
        url = reverse('customer_portal:check_order_status_api', args=['#CE-7777'])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'unpaid')

    def test_anonymous_kiosk_sees_paid_status(self):
        self.order.status = 'pending'
        self.order.save()
        url = reverse('customer_portal:check_order_status_api', args=['#CE-7777'])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'pending')

    def test_kiosk_polls_public_endpoint_not_staff_gated_one(self):
        resp = self.client.get(reverse('customer_portal:kiosk_menu'))
        content = resp.content.decode()
        # The rendered template resolves the URL, so assert on the path and the
        # runtime placeholder the JS swaps for the encoded slip number.
        self.assertIn('/kiosk/api/order-status/KIOKS-PLACEHOLDER/', content)
        self.assertNotIn('process_barcode_api', content)


class OperatingHoursTestCase(TestCase):
    @patch('core_app.utils.is_operating_hours', return_value=False)
    def test_checkout_blocked_outside_operating_hours(self, mock_hours):
        url = reverse('customer_portal:process_checkout')
        resp = self.client.post(
            url,
            data=json.dumps({'cart': [{'id': 1, 'qty': 1}], 'is_delivery': False}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 422)
        self.assertFalse(resp.json()['success'])
