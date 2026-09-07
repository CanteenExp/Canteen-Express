import json
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import CustomUser
from canteen_menu.models import Category, MenuItem

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
