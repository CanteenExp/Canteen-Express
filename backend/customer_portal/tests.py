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
