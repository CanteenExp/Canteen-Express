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
