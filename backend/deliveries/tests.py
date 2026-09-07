import json
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import CustomUser
from customer_portal.models import Order
from deliveries.models import DeliveryRequest, DeliveryMessage

class DeliveryChatTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.faculty_user = CustomUser.objects.create_user(
            username='faculty1',
            password='password123',
            role='FACULTY'
        )
        self.rider_user = CustomUser.objects.create_user(
            username='rider1',
            password='password123',
            role='DELIVERY'
        )
        self.order = Order.objects.create(
            order_number='#CE-9999',
            total_amount=150.00,
            status='pending',
            customer=self.faculty_user
        )
        self.delivery = DeliveryRequest.objects.create(
            order=self.order,
            rider=self.rider_user,
            delivery_location='Admin Building, Room 201',
            status=DeliveryRequest.RequestStatus.ACCEPTED
        )
        self.get_url = reverse('deliveries:get_messages', args=[self.delivery.id])
        self.send_url = reverse('deliveries:send_message', args=[self.delivery.id])

    def test_faculty_and_rider_chat_flow(self):
        # 1. Faculty sends a message
        self.client.login(username='faculty1', password='password123')
        response = self.client.post(
            self.send_url,
            data=json.dumps({'message': 'Hello rider, please deliver to Room 201.'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

        # 2. Rider fetches messages and verifies faculty's message
        self.client.logout()
        self.client.login(username='rider1', password='password123')
        response = self.client.get(self.get_url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['messages']), 1)
        self.assertEqual(data['messages'][0]['message'], 'Hello rider, please deliver to Room 201.')
        self.assertEqual(data['messages'][0]['sender'], 'faculty1')
        self.assertFalse(data['messages'][0]['is_me'])

        # 3. Rider replies to faculty
        response = self.client.post(
            self.send_url,
            data=json.dumps({'message': 'Copy po! On the way na po.'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

        # 4. Faculty fetches messages and verifies rider's reply
        self.client.logout()
        self.client.login(username='faculty1', password='password123')
        response = self.client.get(self.get_url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['messages']), 2)
        self.assertEqual(data['messages'][1]['message'], 'Copy po! On the way na po.')
        self.assertEqual(data['messages'][1]['sender'], 'rider1')
        self.assertFalse(data['messages'][1]['is_me'])


class DeliveryRiderFeatureTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.rider = CustomUser.objects.create_user(
            username='rider2', password='password123', role='DELIVERY',
            first_name='Ronda', last_name='Rider', phone='09170000001'
        )
        self.faculty = CustomUser.objects.create_user(
            username='faculty2', password='password123', role='FACULTY',
            first_name='Faye', last_name='Fac', phone='09170000002'
        )
        self.order = Order.objects.create(
            order_number='#CE-7777', total_amount=250.00, status='accepted',
            customer=self.faculty
        )
        self.delivery = DeliveryRequest.objects.create(
            order=self.order, rider=self.rider, delivery_location='Admin, Room 7',
            status=DeliveryRequest.RequestStatus.ACCEPTED,
            dest_lat=9.77725, dest_lng=118.73480
        )

    def test_pool_status_reports_counts_and_unread(self):
        self.client.login(username='rider2', password='password123')
        DeliveryMessage.objects.create(delivery=self.delivery, sender=self.faculty, message='Kumusta?', is_read=False)
        # A fresh searching request in the pool
        search_order = Order.objects.create(order_number='#CE-7778', total_amount=80.00, status='unpaid')
        DeliveryRequest.objects.create(order=search_order, delivery_location='SHS Bldg, Rm 2',
                                       status=DeliveryRequest.RequestStatus.SEARCHING)

        resp = self.client.get(reverse('deliveries:pool_status'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['pending_count'], 1)
        self.assertEqual(data['total_unread'], 1)
        self.assertEqual(data['unread'][str(self.delivery.id)], 1)

        DeliveryRequest.objects.filter(order__in=[self.order, search_order]).delete()
        Order.objects.filter(id=search_order.id).delete()

    def test_order_detail_returns_items_and_customer(self):
        self.client.login(username='rider2', password='password123')
        resp = self.client.get(reverse('deliveries:order_detail', args=[self.delivery.id]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['order_number'], '#CE-7777')
        self.assertEqual(data['customer_name'], 'Faye Fac')
        self.assertEqual(data['customer_phone'], '09170000002')
        self.assertEqual(float(data['subtotal']), 250.0)

    def test_get_messages_marks_incoming_as_read(self):
        self.client.login(username='rider2', password='password123')
        msg = DeliveryMessage.objects.create(delivery=self.delivery, sender=self.faculty, message='Hi', is_read=False)
        resp = self.client.get(reverse('deliveries:get_messages', args=[self.delivery.id]))
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['unread_count'], 1)
        msg.refresh_from_db()
        self.assertTrue(msg.is_read)

    def test_rider_updates_location_and_tracking_reflects_it(self):
        from deliveries.models import RiderLocationPoint
        self.client.login(username='rider2', password='password123')

        # Two location pushes build a path history
        resp = self.client.post(
            reverse('deliveries:update_location', args=[self.delivery.id]),
            data=json.dumps({'lat': 9.77750, 'lng': 118.73300}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])

        # simulate a second point
        resp = self.client.post(
            reverse('deliveries:update_location', args=[self.delivery.id]),
            data=json.dumps({'lat': 9.77780, 'lng': 118.73360}),
            content_type='application/json'
        )
        self.assertTrue(resp.json()['success'])
        self.assertEqual(RiderLocationPoint.objects.filter(delivery=self.delivery).count(), 2)

        track = self.client.get(reverse('deliveries:get_tracking', args=[self.delivery.id])).json()
        self.assertTrue(track['success'])
        self.assertEqual(float(track['lat']), 9.77780)
        self.assertEqual(float(track['lng']), 118.73360)
        self.assertIsNotNone(track['updated_at'])
        self.assertGreaterEqual(track['speed_kmh'], 0)
        self.assertGreater(track['total_distance_km'], 0)
        self.assertIsNotNone(track['remaining_km'])
        self.assertEqual(float(track['dest_lat']), 9.77725)
        self.assertEqual(float(track['dest_lng']), 118.73480)
        # ETA depends on speed; when slow/stopped it may be None
        self.assertTrue(track['eta_minutes'] is None or isinstance(track['eta_minutes'], int))

        page = self.client.get(reverse('deliveries:track_order', args=[self.delivery.id]))
        self.assertEqual(page.status_code, 200)

    def test_rider_location_push_outside_campus_is_rejected(self):
        self.client.login(username='rider2', password='password123')

        # Far outside the campus geofence -> rejected
        resp = self.client.post(
            reverse('deliveries:update_location', args=[self.delivery.id]),
            data=json.dumps({'lat': 14.5995, 'lng': 120.9842}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 422)
        self.assertFalse(resp.json()['success'])
        from deliveries.models import RiderLocationPoint
        self.assertEqual(RiderLocationPoint.objects.filter(delivery=self.delivery).count(), 0)

        # On-campus push -> accepted
        resp2 = self.client.post(
            reverse('deliveries:update_location', args=[self.delivery.id]),
            data=json.dumps({'lat': 9.77750, 'lng': 118.73300}),
            content_type='application/json'
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertTrue(resp2.json()['success'])


class DeliverySyncTestCase(TestCase):
    """Covers the order->rider synchronization fixes: acceptance race, release
    back to pool, and offline rider enforcement."""

    def setUp(self):
        self.client = Client()
        self.rider_a = CustomUser.objects.create_user(
            username='riderA', password='password123', role='DELIVERY',
            is_available=True
        )
        self.rider_b = CustomUser.objects.create_user(
            username='riderB', password='password123', role='DELIVERY',
            is_available=True
        )
        self.faculty = CustomUser.objects.create_user(
            username='facultySync', password='password123', role='FACULTY'
        )
        self.order = Order.objects.create(
            order_number='#CE-5555', total_amount=120.00, status='pending',
            customer=self.faculty
        )
        self.delivery = DeliveryRequest.objects.create(
            order=self.order, delivery_location='Admin Bldg, Rm 1',
            status=DeliveryRequest.RequestStatus.SEARCHING,
            dest_lat=9.77760, dest_lng=118.73400
        )

    def _login(self, username):
        self.client.login(username=username, password='password123')

    def test_release_back_to_pool_returns_to_searching(self):
        """A canceled ACCEPTED delivery must return to the shared SEARCHING pool
        (not become permanently invisible via REJECTED)."""
        self.delivery.status = DeliveryRequest.RequestStatus.ACCEPTED
        self.delivery.rider = self.rider_a
        self.delivery.accepted_at = None
        self.delivery.save()

        self._login('riderA')
        resp = self.client.get(reverse('deliveries:cancel_delivery', args=[self.delivery.id]))
        self.assertEqual(resp.status_code, 302)  # redirect back to dashboard

        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, DeliveryRequest.RequestStatus.SEARCHING)
        self.assertIsNone(self.delivery.rider)

        # The released delivery is visible again in the incoming pool.
        pending_ids = list(DeliveryRequest.objects.filter(
            status=DeliveryRequest.RequestStatus.SEARCHING).values_list('id', flat=True))
        self.assertIn(self.delivery.id, pending_ids)

    def test_race_condition_only_one_rider_accepts(self):
        """Two riders cannot both accept the same SEARCHING delivery; the first
        wins and the second is blocked (no double assignment)."""
        self._login('riderA')
        resp_a = self.client.get(reverse('deliveries:accept_delivery', args=[self.delivery.id]))
        self.assertEqual(resp_a.status_code, 302)

        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, DeliveryRequest.RequestStatus.ACCEPTED)
        self.assertEqual(self.delivery.rider, self.rider_a)

        # Second rider tries to accept the same (now ACCEPTED) delivery.
        self.client.logout()
        self._login('riderB')
        resp_b = self.client.get(reverse('deliveries:accept_delivery', args=[self.delivery.id]))
        # Should not reassign to rider B; rider A still owns it.
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.rider, self.rider_a)
        self.assertEqual(self.delivery.status, DeliveryRequest.RequestStatus.ACCEPTED)

    def test_offline_rider_cannot_accept(self):
        """An offline rider must not be able to accept an incoming request."""
        self.rider_b.is_available = False
        self.rider_b.save(update_fields=['is_available'])
        self._login('riderB')

        resp = self.client.get(reverse('deliveries:accept_delivery', args=[self.delivery.id]))
        self.assertEqual(resp.status_code, 302)  # redirect with error

        self.delivery.refresh_from_db()
        # Not assigned to the offline rider, still SEARCHING in the pool.
        self.assertEqual(self.delivery.status, DeliveryRequest.RequestStatus.SEARCHING)
        self.assertIsNone(self.delivery.rider)

    def test_raw_status_property_present(self):
        """DeliveryRequest exposes raw_status for the dashboard labels."""
        self.assertEqual(self.delivery.raw_status, DeliveryRequest.RequestStatus.SEARCHING)
        self.delivery.status = DeliveryRequest.RequestStatus.ACCEPTED
        self.assertEqual(self.delivery.raw_status, DeliveryRequest.RequestStatus.ACCEPTED)

    def test_auto_assign_when_rider_comes_online(self):
        """A SEARCHING order with no assigned rider must be handed instantly to
        the first rider who comes online -- no manual hunting required."""
        self.delivery.assigned_to = None
        self.delivery.assigned_at = None
        self.delivery.save(update_fields=['assigned_to', 'assigned_at'])

        # riderB starts offline; going online should immediately pull the
        # waiting order into their own pool.
        self.rider_b.is_available = False
        self.rider_b.save(update_fields=['is_available'])
        self._login('riderB')
        resp = self.client.post(reverse('deliveries:toggle_availability'))
        self.assertTrue(resp.json()['success'])
        self.assertEqual(resp.json()['assigned_order'], self.delivery.order.order_number)

        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.assigned_to, self.rider_b)
        self.assertEqual(self.delivery.status, DeliveryRequest.RequestStatus.SEARCHING)

    def test_auto_assign_does_not_steal_assigned_order(self):
        """Auto-assign must only pull orders with NO assigned rider; it must
        never take an order another rider is already deciding on."""
        self.delivery.assigned_to = self.rider_a
        self.delivery.assigned_at = None
        self.delivery.save(update_fields=['assigned_to', 'assigned_at'])

        self.rider_b.is_available = False
        self.rider_b.save(update_fields=['is_available'])
        self._login('riderB')
        self.client.post(reverse('deliveries:toggle_availability'))

        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.assigned_to, self.rider_a)

    def test_serializer_exposes_assigned_rider(self):
        """The faculty payload must reveal who the order is assigned to the
        instant a rider is found, even before the rider accepts."""
        from .utils import serialize_delivery
        self.delivery.assigned_to = self.rider_a
        self.delivery.save(update_fields=['assigned_to'])

        data = serialize_delivery(self.delivery)
        self.assertEqual(data['raw_status'], DeliveryRequest.RequestStatus.SEARCHING)
        self.assertEqual(data['assigned_rider_name'], self.rider_a.username)
        self.assertIsNotNone(data['dest_lat'])
        self.assertIsNotNone(data['dest_lng'])
