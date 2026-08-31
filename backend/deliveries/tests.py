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
