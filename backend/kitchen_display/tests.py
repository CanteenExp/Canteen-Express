import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from customer_portal.models import Order, OrderItem

User = get_user_model()


class KitchenBoardCancellationTests(TestCase):
    """A cancelled order must vanish from the Kitchen Board and the staff
    dashboard the moment it is cancelled, so staff cannot keep tapping a dead
    order and hit 'Cannot move order from ...' errors."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username='kitchen_staff', password='testpass123', role='STAFF'
        )
        self.client.force_login(self.staff)
        self.active = Order.objects.create(
            order_number='KB1001', total_amount=120.00, status='pending'
        )
        OrderItem.objects.create(
            order=self.active, quantity=1, item_name='Burger', price='120.00'
        )
        self.cancelled = Order.objects.create(
            order_number='KB1002', total_amount=90.00, status='cancelled'
        )

    def test_kitchen_board_hides_cancelled_orders(self):
        response = self.client.get(reverse('kitchen_display:kitchen_board'))
        self.assertContains(response, 'KB1001')
        self.assertNotContains(response, 'KB1002')

    def test_orders_json_hides_cancelled_orders(self):
        response = self.client.get(reverse('kitchen_display:kitchen_orders_json_api'))
        self.assertEqual(response.status_code, 200)
        boards = json.loads(response.content)['boards']
        numbers = {
            o['order_number']
            for column in boards.values() for o in column
        }
        self.assertIn('KB1001', numbers)
        self.assertNotIn('KB1002', numbers)

    def test_staff_dashboard_recent_orders_hides_cancelled(self):
        response = self.client.get(reverse('kitchen_display:dashboard'))
        self.assertNotContains(response, 'KB1002')

    def test_cancelled_order_cannot_move_to_ready(self):
        response = self.client.post(
            reverse('kitchen_display:update_status', args=[self.cancelled.id]),
            data=json.dumps({'status': 'ready'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        payload = json.loads(response.content)
        self.assertFalse(payload['success'])
        self.assertIn('cancelled', payload['error'])

    def test_kitchen_board_renders_status_dialog(self):
        response = self.client.get(reverse('kitchen_display:kitchen_board'))
        self.assertContains(response, 'id="status-dialog"')
        self.assertContains(response, 'showStatusDialog(')
        # The backend never falls back to a browser alert() anymore.
        self.assertNotContains(response, "alert('Error:")