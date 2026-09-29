import json
import re
from django.conf import settings
from django.test import TestCase, Client, SimpleTestCase, override_settings
from django.urls import reverse
from accounts.models import CustomUser
from customer_portal.models import Order
from deliveries.models import DeliveryRequest, DeliveryMessage, RiderLocationPoint

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
        # Two location pushes: history points are throttled to one per 4s so
        # watchPosition bursts don't blow up the table, but the LIVE
        # coordinates always update immediately (asserted below).
        self.assertGreaterEqual(RiderLocationPoint.objects.filter(delivery=self.delivery).count(), 1)

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

    @override_settings(ENFORCE_GEOFENCE=True)
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

    def test_going_online_does_not_preassign_order(self):
        """Going online must NOT hand the order to the rider: SEARCHING
        deliveries are shared proposals in the pool, and only accepting assigns
        one."""
        self.delivery.assigned_to = None
        self.delivery.assigned_at = None
        self.delivery.save(update_fields=['assigned_to', 'assigned_at'])

        # riderB starts offline; going online should make the order VISIBLE,
        # not assigned to them.
        self.rider_b.is_available = False
        self.rider_b.save(update_fields=['is_available'])
        self._login('riderB')
        resp = self.client.post(reverse('deliveries:toggle_availability'))
        self.assertTrue(resp.json()['success'])
        self.assertIsNone(resp.json()['assigned_order'])

        self.delivery.refresh_from_db()
        self.assertIsNone(self.delivery.assigned_to)
        self.assertEqual(self.delivery.status, DeliveryRequest.RequestStatus.SEARCHING)

        # Still visible to every rider in the shared proposal pool.
        from .utils import pending_pool_for_rider
        self.rider_b.refresh_from_db()
        self.assertEqual(self.delivery.id, pending_pool_for_rider(self.rider_b).first().id)

    def test_going_online_does_not_steal_assigned_order(self):
        """Going online must never reassign an order another rider is still
        deciding on (proposal-only model)."""
        self.delivery.assigned_to = self.rider_a
        self.delivery.assigned_at = None
        self.delivery.save(update_fields=['assigned_to', 'assigned_at'])

        self.rider_b.is_available = False
        self.rider_b.save(update_fields=['is_available'])
        self._login('riderB')
        self.client.post(reverse('deliveries:toggle_availability'))

        self.delivery.refresh_from_db()
        # The order is still a shared proposal: either rider may see it, but the
        # direct assignment reference is only legacy and the next sweep clears
        # it -- nobody 'owns' it before accepting.
        self.assertEqual(self.delivery.status, DeliveryRequest.RequestStatus.SEARCHING)

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

    def test_expire_never_preassigns_order(self):
        """A SEARCHING delivery stays an unassigned proposal after the sweep --
        no rider is designated before accepting."""
        from django.utils import timezone as tz
        from .views import expire_stale_requests
        self.delivery.assigned_to = None
        self.delivery.assigned_at = None
        self.delivery.requested_at = tz.now() - tz.timedelta(minutes=1)
        self.delivery.save(update_fields=['assigned_to', 'assigned_at', 'requested_at'])

        expire_stale_requests()

        self.delivery.refresh_from_db()
        self.assertIsNone(self.delivery.assigned_to)
        self.assertIsNone(self.delivery.assigned_at)
        self.assertEqual(self.delivery.status, DeliveryRequest.RequestStatus.SEARCHING)

    def test_expire_clears_stale_offer_keeps_proposal_visible(self):
        """A stale 'offered' rider is cleared by the sweep so the delivery reads
        as a shared proposal for everyone; it is never forced onto one rider and
        never times out while riders are online."""
        from django.utils import timezone as tz
        from .views import expire_stale_requests
        self.delivery.assigned_to = self.rider_a
        self.delivery.assigned_at = tz.now() - tz.timedelta(seconds=60)
        self.delivery.save(update_fields=['assigned_to', 'assigned_at'])

        expire_stale_requests()

        self.delivery.refresh_from_db()
        self.assertIsNone(self.delivery.assigned_to)
        self.assertIsNone(self.delivery.assigned_at)
        self.assertEqual(self.delivery.status, DeliveryRequest.RequestStatus.SEARCHING)

    def test_expire_keeps_proposal_when_only_one_rider_online(self):
        """With any rider online, the proposal stays visible (never dropped to
        TIMEOUT and never pre-assigned), even for a very old request."""
        from django.utils import timezone as tz
        from .views import expire_stale_requests
        self.rider_a.is_available = False
        self.rider_a.save(update_fields=['is_available'])
        # rider_b stays online: give a fresh presence heartbeat so the sweep
        # treats them as genuinely connected.
        self.rider_b.availability_updated_at = tz.now()
        self.rider_b.save(update_fields=['availability_updated_at'])
        self.delivery.assigned_to = self.rider_a
        self.delivery.assigned_at = tz.now() - tz.timedelta(seconds=60)
        self.delivery.save(update_fields=['assigned_to', 'assigned_at'])

        expire_stale_requests()

        self.delivery.refresh_from_db()
        self.assertIsNone(self.delivery.assigned_to)
        self.assertEqual(self.delivery.status, DeliveryRequest.RequestStatus.SEARCHING)

        # Even a very old proposal is not auto-dropped while a rider is online.
        self.delivery.requested_at = tz.now() - tz.timedelta(minutes=30)
        self.delivery.save(update_fields=['requested_at'])
        expire_stale_requests()
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, DeliveryRequest.RequestStatus.SEARCHING)

    def test_expire_times_out_only_true_orphans(self):
        """An order nobody could ever be assigned to (no rider online for a
        while) eventually TIMEOUTs so the queue stays clean."""
        from django.utils import timezone as tz
        from .views import expire_stale_requests
        self.rider_a.is_available = False
        self.rider_a.save(update_fields=['is_available'])
        self.rider_b.is_available = False
        self.rider_b.save(update_fields=['is_available'])
        self.delivery.assigned_to = None
        self.delivery.assigned_at = None
        self.delivery.requested_at = tz.now() - tz.timedelta(minutes=10)
        self.delivery.save(update_fields=['assigned_to', 'assigned_at', 'requested_at'])

        expire_stale_requests()

        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, DeliveryRequest.RequestStatus.TIMEOUT)


class RoadRoutingTestCase(TestCase):
    """The routing helpers must work without ever touching the network."""

    def test_decode_polyline_round_trip(self):
        from .routing import decode_polyline
        # A real Valhalla shape (precision 6) for a campus route, so this pins
        # the decoder against known-good coordinates rather than against itself.
        shape = r'{gxsQec|maF@_JEci@xh@yB~k@cCaIwPkDmHqDeHo@`AoA\wABuFaAuE_BQO'
        path = decode_polyline(shape)
        self.assertEqual(len(path), 14)
        self.assertAlmostEqual(path[0][0], 9.777806, places=5)
        self.assertAlmostEqual(path[0][1], 118.733379, places=5)
        self.assertAlmostEqual(path[-1][0], 9.777102, places=5)
        self.assertAlmostEqual(path[-1][1], 118.734977, places=5)
        # Every point stays on the campus and the path travels east.
        for lat, lng in path:
            self.assertTrue(9.776 < lat < 9.779)
            self.assertTrue(118.733 < lng < 118.736)
        self.assertGreater(path[-1][1], path[0][1])

    def test_get_road_route_is_disabled_during_tests(self):
        """No outbound call may ever happen from the test suite."""
        from .routing import get_road_route
        self.assertIsNone(get_road_route(9.77800, 118.73338, 9.77725, 118.73480))

    def test_get_road_route_requires_both_endpoints(self):
        from .routing import get_road_route
        self.assertIsNone(get_road_route(9.77800, 118.73338, None, None))

    @override_settings(ROUTING_ENABLED=False)
    def test_routing_can_be_switched_off_by_setting(self):
        from .routing import get_road_route
        self.assertIsNone(get_road_route(9.77800, 118.73338, 9.77725, 118.73480))

    def test_tracking_payload_exposes_path_keys(self):
        """The map falls back to a straight line, so the keys must always exist
        even when no provider answered."""
        from accounts.models import CustomUser
        from django.core.cache import cache
        cache.clear()
        rider = CustomUser.objects.create_user(
            username='route_rider', password='password123', role='DELIVERY'
        )
        order = Order.objects.create(
            order_number='#CE-7777', total_amount=100.00, status='pending'
        )
        delivery = DeliveryRequest.objects.create(
            order=order, rider=rider, delivery_location='Gymnasium',
            status=DeliveryRequest.RequestStatus.ACCEPTED,
            dest_lat=9.77725, dest_lng=118.73480,
            rider_lat=9.77800, rider_lng=118.73338,
        )
        self.client.login(username='route_rider', password='password123')
        data = self.client.get(
            reverse('deliveries:get_tracking', args=[delivery.id])).json()
        self.assertTrue(data['success'])
        self.assertIn('path', data)
        self.assertIn('routing_provider', data)
        # Routing is off in tests, so the map gets the straight-line fallback and
        # remaining_km stays the haversine value.
        self.assertIsNone(data['path'])
        self.assertIsNone(data['routing_provider'])
        self.assertIsNotNone(data['remaining_km'])

    def test_route_total_is_measured_from_the_first_recorded_fix(self):
        """Progress is (route_total_km - remaining_km) / route_total_km, so the
        total must be the length of the real pickup->drop-off trip -- taken from
        the rider's FIRST fix (the canteen), not a hard-coded canteen coordinate
        that could coincide with the customer's own drop-off."""
        from accounts.models import CustomUser
        from deliveries.models import RiderLocationPoint
        from deliveries.utils import haversine_km
        from django.core.cache import cache
        cache.clear()
        rider = CustomUser.objects.create_user(
            username='progress_rider', password='password123', role='DELIVERY'
        )
        order = Order.objects.create(
            order_number='#CE-8888', total_amount=100.00, status='pending'
        )
        dest_lat, dest_lng = 9.77725, 118.73480
        # First fix = canteen pickup. Second fix = rider a little closer.
        start_lat, start_lng = 9.77800, 118.73338
        mid_lat, mid_lng = 9.77760, 118.73410
        delivery = DeliveryRequest.objects.create(
            order=order, rider=rider, delivery_location='Library',
            status=DeliveryRequest.RequestStatus.ACCEPTED,
            dest_lat=dest_lat, dest_lng=dest_lng,
            rider_lat=mid_lat, rider_lng=mid_lng,
        )
        RiderLocationPoint.objects.create(
            delivery=delivery, rider=rider, lat=start_lat, lng=start_lng)
        RiderLocationPoint.objects.create(
            delivery=delivery, rider=rider, lat=mid_lat, lng=mid_lng)

        self.client.login(username='progress_rider', password='password123')
        data = self.client.get(
            reverse('deliveries:get_tracking', args=[delivery.id])).json()
        # Routing is disabled in tests, so both fall back to haversine.
        expected_total = haversine_km(start_lat, start_lng, dest_lat, dest_lng)
        self.assertAlmostEqual(data['route_total_km'], expected_total, places=2)
        # The total describes the whole trip, so it must be the LONGER of the two
        # legs -- never the shorter remaining leg.
        self.assertGreater(data['route_total_km'], data['remaining_km'])
        pct = round(
            ((data['route_total_km'] - data['remaining_km']) / data['route_total_km']) * 100)
        self.assertTrue(0 < pct < 100, f"expected mid-trip progress, got {pct}%")

    def test_route_total_is_none_before_the_first_fix(self):
        """With no history yet there is no trip origin, so the client must fall
        back to seeding the total from the first remaining_km it sees."""
        from accounts.models import CustomUser
        from django.core.cache import cache
        cache.clear()
        rider = CustomUser.objects.create_user(
            username='noorigin_rider', password='password123', role='DELIVERY'
        )
        order = Order.objects.create(
            order_number='#CE-9999', total_amount=100.00, status='pending'
        )
        delivery = DeliveryRequest.objects.create(
            order=order, rider=rider, delivery_location='Gymnasium',
            status=DeliveryRequest.RequestStatus.ACCEPTED,
            dest_lat=9.77725, dest_lng=118.73480,
            rider_lat=9.77800, rider_lng=118.73338,
        )
        self.client.login(username='noorigin_rider', password='password123')
        data = self.client.get(
            reverse('deliveries:get_tracking', args=[delivery.id])).json()
        self.assertIsNone(data['route_total_km'])


class GpsAccuracyTestCase(TestCase):
    """GPS quality gate: a fuzzy fix must never move the rider on the map."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.rider = CustomUser.objects.create_user(
            username='acc_rider', password='password123', role='DELIVERY'
        )
        self.order = Order.objects.create(
            order_number='#CE-8100', total_amount=100.00, status='pending'
        )
        self.delivery = DeliveryRequest.objects.create(
            order=self.order, rider=self.rider, delivery_location='Gymnasium',
            status=DeliveryRequest.RequestStatus.ACCEPTED,
            dest_lat=9.77725, dest_lng=118.73480,
            rider_lat=9.77800, rider_lng=118.73338,
        )
        self.client.login(username='acc_rider', password='password123')
        self.url = reverse('deliveries:update_location', args=[self.delivery.id])

    def _push(self, **overrides):
        payload = {'lat': 9.77810, 'lng': 118.73350}
        payload.update(overrides)
        return self.client.post(
            self.url, json.dumps(payload), content_type='application/json')

    def test_accurate_fix_is_stored_and_exposed(self):
        res = self._push(accuracy=8.5)
        self.assertEqual(res.status_code, 200)
        self.delivery.refresh_from_db()
        self.assertAlmostEqual(self.delivery.rider_acc, 8.5, places=1)
        self.assertEqual(self.delivery.location_points.count(), 1)
        point = self.delivery.location_points.first()
        self.assertAlmostEqual(point.accuracy, 8.5, places=1)

    def test_fuzzy_fix_is_rejected_and_last_good_position_kept(self):
        self._push(accuracy=8.5)
        res = self._push(lat=9.77950, lng=118.73450, accuracy=250)
        self.assertEqual(res.status_code, 422)
        body = res.json()
        self.assertFalse(body['success'])
        self.assertTrue(body['ignored'])
        self.assertEqual(body['max_accuracy_m'], 40)
        # The rider must NOT have jumped to the noisy fix.
        self.delivery.refresh_from_db()
        self.assertAlmostEqual(self.delivery.rider_lat, 9.77810, places=5)
        self.assertAlmostEqual(self.delivery.rider_acc, 8.5, places=1)

    def test_missing_accuracy_is_accepted_for_older_devices(self):
        """Devices that do not report accuracy must still be able to push."""
        res = self._push()
        self.assertEqual(res.status_code, 200)
        self.delivery.refresh_from_db()
        self.assertIsNone(self.delivery.rider_acc)

    def test_nonsense_accuracy_is_treated_as_unreported(self):
        res = self._push(accuracy=-5)
        self.assertEqual(res.status_code, 200)
        self.delivery.refresh_from_db()
        self.assertIsNone(self.delivery.rider_acc)

    def test_accuracy_threshold_is_configurable(self):
        with override_settings(GPS_MAX_ACCURACY_M=500):
            res = self._push(accuracy=250)
            self.assertEqual(res.status_code, 200)

    def test_tracking_payload_reports_accuracy(self):
        self._push(accuracy=12.0)
        data = self.client.get(
            reverse('deliveries:get_tracking', args=[self.delivery.id])).json()
        self.assertAlmostEqual(data['accuracy_m'], 12.0, places=1)


class TrackingStreamTestCase(TestCase):
    """The customer tracking page is pushed over SSE, with the 4s poll as the
    fallback. Both must expose the identical payload shape."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.customer = CustomUser.objects.create_user(
            username='track_owner', password='password123', role='STUDENT'
        )
        self.stranger = CustomUser.objects.create_user(
            username='track_stranger', password='password123', role='STUDENT'
        )
        self.rider = CustomUser.objects.create_user(
            username='stream_rider', password='password123', role='DELIVERY'
        )
        self.order = Order.objects.create(
            order_number='#CE-8200', total_amount=100.00, status='pending',
            customer=self.customer,
        )
        self.delivery = DeliveryRequest.objects.create(
            order=self.order, rider=self.rider, delivery_location='Library',
            status=DeliveryRequest.RequestStatus.ACCEPTED,
            dest_lat=9.77725, dest_lng=118.73480,
            rider_lat=9.77800, rider_lng=118.73338, rider_acc=10.0,
        )
        self.url = reverse('deliveries:tracking_stream', args=[self.delivery.id])

    def test_owner_receives_event_stream(self):
        self.client.login(username='track_owner', password='password123')
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'text/event-stream')
        self.assertEqual(res['Cache-Control'], 'no-cache')
        # Read only the first frame so the test never blocks on the open stream.
        frame = next(res.streaming_content).decode()
        self.assertTrue(frame.startswith('data: '))
        payload = json.loads(frame[len('data: '):])
        self.assertTrue(payload['success'])
        self.assertEqual(payload['order_number'], self.order.order_number)

    def test_stream_payload_matches_polling_payload_shape(self):
        self.client.login(username='track_owner', password='password123')
        frame = next(self.client.get(self.url).streaming_content).decode()
        pushed = json.loads(frame[len('data: '):])
        polled = self.client.get(
            reverse('deliveries:get_tracking', args=[self.delivery.id])).json()
        self.assertEqual(sorted(pushed), sorted(polled))

    def test_stream_denied_to_other_customers(self):
        self.client.login(username='track_stranger', password='password123')
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_stream_denied_to_anonymous(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_location_push_bumps_the_stream_version(self):
        from django.core.cache import cache
        from deliveries.views import tracking_version_key
        self.client.login(username='stream_rider', password='password123')
        self.client.post(
            reverse('deliveries:update_location', args=[self.delivery.id]),
            json.dumps({'lat': 9.77811, 'lng': 118.73351, 'accuracy': 9.0}),
            content_type='application/json')
        self.assertIsNotNone(cache.get(tracking_version_key(self.delivery.id)))

class RiderRoutePayloadTestCase(TestCase):
    """The tracking payload carries the rider's route only.

    The map draws a single solid orange line for the rider's route: the live
    remaining leg when the server could route it, or a dashed straight line when
    routing is down. A separate whole-trip "campus route" layer and a
    calculation-details panel were both removed at the user's request, so this
    pins that neither silently comes back. Routing is stubbed here because the
    suite must not touch the network.
    """

    def setUp(self):
        from accounts.models import CustomUser
        from django.core.cache import cache
        cache.clear()
        self.rider = CustomUser.objects.create_user(
            username='route_rider', password='testpass', role='DELIVERY')
        self.order = Order.objects.create(
            order_number='#CE-6600', total_amount=100.00, status='pending')
        self.delivery = DeliveryRequest.objects.create(
            order=self.order, rider=self.rider, delivery_location='Library',
            status=DeliveryRequest.RequestStatus.ACCEPTED,
            dest_lat=9.77725, dest_lng=118.73480,
            rider_lat=9.77790, rider_lng=118.73350)
        # The trip origin is the rider's FIRST recorded fix.
        RiderLocationPoint.objects.create(
            delivery=self.delivery, rider=self.rider,
            lat=9.77810, lng=118.73320, speed_kmh=12.0, accuracy=8.0)

    def _stub_route(self, patch_target):
        from unittest import mock
        def fake(origin_lat, origin_lng, dest_lat, dest_lng):
            return {
                'path': [[origin_lat, origin_lng], [9.77760, 118.73410],
                         [dest_lat, dest_lng]],
                'distance_km': 0.42,
                'duration_min': 6.0,
                'provider': 'stub',
            }
        return mock.patch(patch_target, side_effect=fake)

    def test_payload_carries_rider_route_and_no_campus_layer(self):
        import deliveries.views as dv
        with self._stub_route('deliveries.views.get_road_route'):
            payload = dv._tracking_payload(self.delivery)
        # The orange rider route is present and routed.
        self.assertIsNotNone(payload['path'])
        self.assertGreater(len(payload['path']), 1)
        self.assertEqual(payload['routing_provider'], 'stub')
        self.assertEqual(payload['route_duration_min'], 6)
        # The progress denominator is still derived from the real trip.
        self.assertIsNotNone(payload['route_total_km'])
        self.assertAlmostEqual(payload['route_total_km'], 0.42, places=2)
        # The removed campus-route keys must stay gone.
        for key in ('campus_path', 'campus_provider', 'campus_duration_min',
                    'is_campus_routed', 'is_road_routed'):
            self.assertNotIn(key, payload)

    def test_routing_outage_degrades_to_straight_line(self):
        """When routing is unavailable the map still gets coordinates, and
        route_total_km falls back to haversine instead of vanishing."""
        self.client.force_login(self.rider)
        data = self.client.get(
            reverse('deliveries:get_tracking', args=[self.delivery.id])).json()
        self.assertTrue(data['success'])
        self.assertIsNone(data['path'])
        self.assertIsNone(data['routing_provider'])
        # Straight-line estimate still drives the progress bar.
        self.assertIsNotNone(data['route_total_km'])
        # ...and the card is told to label those figures as approximate, so a
        # shorter-than-real crow-flight distance is never shown as exact.
        self.assertTrue(data['distance_is_approximate'])

    def test_routed_delivery_is_not_flagged_approximate(self):
        """A real road route means the figures are exact, so no "approx." badge."""
        import deliveries.views as dv
        with self._stub_route('deliveries.views.get_road_route'):
            payload = dv._tracking_payload(self.delivery)
        self.assertFalse(payload['distance_is_approximate'])

    def test_payload_carries_travelled_trail(self):
        """The ridden ground is served from the DB, not rebuilt in the browser.

        The previous breadcrumb only ever contained fixes that arrived while the
        tracking page happened to be open, so it restarted empty on every reload.
        """
        import deliveries.views as dv
        for lat, lng in ((9.77780, 118.73360), (9.77740, 118.73410)):
            RiderLocationPoint.objects.create(
                delivery=self.delivery, rider=self.rider,
                lat=lat, lng=lng, speed_kmh=11.0, accuracy=7.0)
        with self._stub_route('deliveries.views.get_road_route'):
            payload = dv._tracking_payload(self.delivery)
        trail = payload['trail']
        self.assertGreaterEqual(len(trail), 2)
        # Starts at the recorded pickup and ends at the rider's live position.
        self.assertAlmostEqual(trail[0][0], 9.77810, places=4)
        self.assertAlmostEqual(trail[-1][1], 118.73350, places=4)
        # Coordinates are [lat, lng] pairs rounded to 5dp, JSON-serialisable.
        self.assertIsInstance(json.dumps(trail), str)

    def test_trail_is_thinned_and_bounded(self):
        """A stationary rider collapses to a short trail instead of hundreds of
        jittery fixes, and a long trip cannot bloat the payload."""
        from deliveries.utils import thin_trail
        # Sub-metre wobble (~0.06 m per fix): what a phone reports while parked.
        parked = [(9.77778 + i * 0.0000005, 118.73333) for i in range(120)]
        self.assertLessEqual(len(thin_trail(parked)), 4)
        # ~22 m per fix: genuine travel, so it must NOT be thinned away.
        moving = [(9.77778 + i * 0.0002, 118.73333) for i in range(400)]
        trail = thin_trail(moving)
        self.assertLessEqual(len(trail), 180)
        # Endpoints always survive the thinning.
        self.assertEqual(trail[0], moving[0])
        self.assertEqual(trail[-1], moving[-1])

    def test_tracking_page_draws_only_the_orange_route(self):
        self.client.force_login(self.rider)
        res = self.client.get(
            reverse('deliveries:track_order', args=[self.delivery.id]))
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        # The single orange route line, driven by the payload's `path`.
        self.assertIn("#FF6117", html)
        self.assertIn("data.path", html)
        # The travelled track is drawn from the server payload, not a local
        # accumulator, and stays dimmer than the live route.
        self.assertIn("data.trail", html)
        self.assertIn("opacity: 0.35", html)
        # The route legend overlay was removed at the user's request; the map is
        # meant to read on its own.
        for removed in ('Route legend', 'Already travelled', 'Rider route',
                        'fa-route'):
            self.assertNotIn(removed, html)
        # Approximate-distance labelling is wired to the server flag.
        self.assertIn("distance_is_approximate", html)
        self.assertIn("approx-badge", html)
        # No campus route layer, no calculation panel.
        for removed in ('campus_path', 'Campus route (shortest)',
                        'calc-total-val', 'calc-covered-val', 'calc-basis'):
            self.assertNotIn(removed, html)
        # Recenter control is present and wired to the recenter() handler.
        self.assertIn("ce-recenter", html)
        self.assertIn("recenter()", html)
        # The recenter button's styling must survive CSS parsing: a "//" comment
        # in the <style> block used to swallow the whole .ce-recenter a rule.
        self.assertIn(".ce-recenter a {", html)


class TileProviderPolicyTestCase(SimpleTestCase):
    """Guard the basemap tile host and the subdomain list.

    Standard OSM raster tiles are the only keyless provider verified to return
    real per-location tiles at z19 for this campus, which is what makes building
    footprints render when the map is zoomed in. Verified by hashing four
    adjacent tiles at z17/18/19 near the campus centre: OSM gave four distinct
    tiles at every zoom, while Esri's World_Street_Map collapsed to one
    identical tile from z18 and its World_Imagery from z17 -- that placeholder
    is literally the "Map data not yet available" graphic the user reported --
    and CARTO's keyless basemaps returned one identical tile for every location
    and style at every zoom.

    An earlier note here claimed OSM was blocked. That was a testing artefact:
    OSM rejects requests that send no User-Agent, and the check that produced
    that conclusion was a scripted fetch without one. Browsers always send a
    User-Agent, so standard tiles are correct here.
    """

    BLOCKED_HOSTS = ('server.arcgisonline.com', 'basemaps.cartocdn.com')
    EXPECTED_HOST = 'tile.openstreetmap.org'
    # OSM runs a/b/c only. 'd' does not resolve, so listing it makes every
    # fourth tile request fail and leaves grey holes across the map.
    FORBIDDEN_SUBDOMAINS = ('abcd',)

    def _sources(self):
        from pathlib import Path
        base = Path(settings.BASE_DIR)
        roots = [base / 'templates', base / 'static' / 'js',
                 base / 'accounts' / 'templates']
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob('*'):
                if path.suffix in ('.html', '.js') and path.is_file():
                    yield path

    @staticmethod
    def _code_only(text):
        """Drop comment lines.

        The blocked hosts are named on purpose in comments explaining why they
        are not used, so scanning raw text would always fail. Only real code
        (a tile layer, a config default) must be free of them.
        """
        markers = ('//', '*', '#', '<!--')
        return '\n'.join(
            line for line in text.splitlines()
            if not line.strip().startswith(markers))

    def test_no_blocked_tile_host_is_referenced(self):
        offenders = []
        for path in self._sources():
            text = self._code_only(
                path.read_text(encoding='utf-8', errors='ignore'))
            for host in self.BLOCKED_HOSTS:
                if host in text:
                    offenders.append('%s -> %s' % (path.name, host))
        self.assertEqual(
            offenders, [],
            'Blocked/broken tile hosts referenced: %s' % offenders)

    def test_every_tile_layer_uses_the_verified_provider(self):
        layers = 0
        for path in self._sources():
            text = path.read_text(encoding='utf-8', errors='ignore')
            for match in re.finditer(r"L\.tileLayer\(\s*'([^']+)'", text):
                layers += 1
                self.assertIn(
                    self.EXPECTED_HOST, match.group(1),
                    'Tile layer in %s uses an unverified host: %s'
                    % (path.name, match.group(1)))
        # Guards against the test passing simply because no layer was found.
        self.assertGreaterEqual(layers, 5)

    def test_no_dead_tile_subdomain_is_requested(self):
        offenders = []
        for path in self._sources():
            text = path.read_text(encoding='utf-8', errors='ignore')
            for bad in self.FORBIDDEN_SUBDOMAINS:
                if re.search(r"subdomains:\s*['\"]%s['\"]" % bad, text):
                    offenders.append('%s -> %s' % (path.name, bad))
        self.assertEqual(
            offenders, [],
            'Tile layers requesting non-existent OSM subdomains: %s' % offenders)
