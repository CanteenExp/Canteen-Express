import json
from datetime import timedelta

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from customer_portal.models import Order

from .models import ActivityLog
from .services import log_activity, log_menu_change

API_URL = reverse('activity_log:activity_log_api')


class ActivityLogModelTestCase(TestCase):
    def test_create_and_str(self):
        row = ActivityLog.objects.create(
            actor_label='Juan Dela Cruz',
            category=ActivityLog.Category.ORDER,
            level=ActivityLog.Level.SUCCESS,
            action='Confirmed payment for #CE-100',
            target='#CE-100',
            metadata={'total': 65.0},
        )
        self.assertIsNotNone(row.pk)
        self.assertIn('Juan Dela Cruz', str(row))

    def test_ordering_newest_first(self):
        first = ActivityLog.objects.create(
            actor_label='A', category=ActivityLog.Category.MENU,
            action='Added Adobo', level=ActivityLog.Level.INFO,
        )
        second = ActivityLog.objects.create(
            actor_label='B', category=ActivityLog.Category.ORDER,
            action='Moved order', level=ActivityLog.Level.INFO,
        )
        rows = list(ActivityLog.objects.all())
        self.assertEqual(rows[0].pk, second.pk)
        self.assertEqual(rows[1].pk, first.pk)

    def test_soft_delete_fields_do_not_exist(self):
        # The model is deliberately append-only; a hidden log is not an audit trail.
        self.assertFalse(hasattr(ActivityLog(), 'is_active'))
        self.assertFalse(hasattr(ActivityLog(), 'deleted'))


class LogActivityServiceTestCase(TestCase):
    def setUp(self):
        self.staff = CustomUser.objects.create_user(
            username='svc_staff', password='testpass', role='STAFF',
            first_name='Maria', last_name='Santos',
        )

    def test_resolves_actor_and_label_from_request(self):
        self.client.login(username='svc_staff', password='testpass')
        request = self.client.get(API_URL).wsgi_request
        row = log_activity(
            request=request, action='Log in', category=ActivityLog.Category.SYSTEM)
        self.assertIsNotNone(row)
        self.assertEqual(row.actor, self.staff)
        self.assertEqual(row.actor_label, 'Maria Santos')

    def test_never_raises_on_unserializable_actor(self):
        # A total doppelganger that breaks FK/DB constraints must not bubble up.
        row = log_activity(actor=object(), action='boom', category=ActivityLog.Category.SYSTEM)
        self.assertIsNone(row)

    def test_never_raises_on_bad_metadata(self):
        row = log_activity(
            action='odd', category=ActivityLog.Category.SYSTEM, metadata='not-a-dict')
        self.assertIsNotNone(row)
        self.assertEqual(row.metadata, {'value': 'not-a-dict'})

    def test_truncates_long_action_and_target(self):
        row = log_activity(
            action='x' * 500, category=ActivityLog.Category.SYSTEM, target='y' * 500)
        self.assertEqual(len(row.action), 255)
        self.assertEqual(len(row.target), 200)

    def test_menu_change_wrapper(self):
        from canteen_menu.models import MenuItem, Category
        cat = Category.objects.create(name='Grill', description='')
        item = MenuItem.objects.create(name='Bulalo', category=cat, price=150, stock=10)
        row = log_menu_change(None, item, 'Updated Bulalo', metadata={'changes': {'price': {'from': 140, 'to': 150}}})
        self.assertEqual(row.category, ActivityLog.Category.MENU)
        self.assertEqual(row.target, 'Bulalo')


class ActivityLogAPITestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = CustomUser.objects.create_user(
            username='log_staff', password='testpass', role='STAFF',
        )
        self.rider = CustomUser.objects.create_user(
            username='log_rider', password='testpass', role='RIDER',
        )

    def _make(self, **kw):
        base = dict(category=ActivityLog.Category.SYSTEM, level=ActivityLog.Level.INFO,
                    action='Generic action')
        base.update(kw)
        return ActivityLog.objects.create(**base)

    def test_anonymous_is_denied(self):
        res = self.client.get(API_URL, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res.status_code, 401)

    def test_non_staff_is_denied(self):
        self.client.login(username='log_rider', password='testpass')
        res = self.client.get(API_URL, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res.status_code, 403)

    def test_staff_can_fetch(self):
        self.client.login(username='log_staff', password='testpass')
        self._make(action='Made available: Adobo',
                   category=ActivityLog.Category.MENU,
                   level=ActivityLog.Level.INFO,
                   target='Adobo',
                   actor=self.staff,
                   actor_label='log_staff')
        res = self.client.get(API_URL, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['total'], 1)
        row = data['results'][0]
        self.assertEqual(row['action'], 'Made available: Adobo')
        self.assertEqual(row['category'], 'MENU')
        self.assertEqual(row['level'], 'INFO')
        self.assertEqual(row['actor'], 'log_staff')
        self.assertEqual(row['actor_id'], self.staff.pk)
        self.assertIn('created_display', row)
        self.assertIn('created_at', row)

    def test_category_filter(self):
        self.client.login(username='log_staff', password='testpass')
        self._make(action='order action', category=ActivityLog.Category.ORDER)
        self._make(action='menu action', category=ActivityLog.Category.MENU)
        res = self.client.get(API_URL, {'category': 'MENU'},
                              HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        data = res.json()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['results'][0]['action'], 'menu action')

    def test_unknown_category_returns_empty_not_500(self):
        self.client.login(username='log_staff', password='testpass')
        self._make(action='order action', category=ActivityLog.Category.ORDER)
        res = self.client.get(API_URL, {'category': 'BOGUS'},
                              HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['total'], 0)

    def test_level_filter(self):
        self.client.login(username='log_staff', password='testpass')
        self._make(action='info thing', level=ActivityLog.Level.INFO)
        self._make(action='danger thing', level=ActivityLog.Level.DANGER)
        res = self.client.get(API_URL, {'level': 'DANGER'},
                              HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res.json()['total'], 1)

    def test_days_filter(self):
        self.client.login(username='log_staff', password='testpass')
        old = self._make(action='stale entry')
        ActivityLog.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=30))
        self._make(action='recent entry')
        res = self.client.get(API_URL, {'days': '7'},
                              HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        data = res.json()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['results'][0]['action'], 'recent entry')

    def test_search_filter(self):
        self.client.login(username='log_staff', password='testpass')
        self._make(action='Marked unavailable: Turon', category=ActivityLog.Category.MENU)
        self._make(action='Marked unavailable: Adobo', category=ActivityLog.Category.MENU)
        res = self.client.get(API_URL, {'q': 'Turon'},
                              HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res.json()['total'], 1)

    def test_pagination(self):
        self.client.login(username='log_staff', password='testpass')
        for i in range(26):
            self._make(action=f'entry {i}')
        res = self.client.get(API_URL, {'page_size': '10', 'page': '2'},
                              HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        data = res.json()
        self.assertEqual(data['total'], 26)
        self.assertEqual(data['num_pages'], 3)
        self.assertEqual(data['page'], 2)
        self.assertEqual(len(data['results']), 10)
        self.assertTrue(data['has_next'])
        self.assertTrue(data['has_previous'])


class ActivityLogIntegrationTestCase(TestCase):
    """Real flows must leave a trail behind."""

    def setUp(self):
        self.client = Client()
        self.staff = CustomUser.objects.create_user(
            username='int_staff', password='testpass', role='STAFF',
        )
        self.client.login(username='int_staff', password='testpass')
        self.order = Order.objects.create(
            order_number='#CE-5151', total_amount=120.00, status='unpaid')

    def test_confirm_payment_logs_payment_entry(self):
        res = self.client.post(
            reverse('canteen_menu:process_barcode_api'),
            data=json.dumps({'action': 'confirm_payment', 'order_id': '#CE-5151'}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        rows = ActivityLog.objects.filter(category=ActivityLog.Category.PAYMENT)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows[0].actor, self.staff)
        self.assertIn('#CE-5151', rows[0].action)
        self.assertEqual(rows[0].metadata.get('order_id'), self.order.pk)

    def test_kitchen_status_change_logs_order_entry(self):
        res = self.client.post(
            reverse('kitchen_display:update_status', args=[self.order.pk]),
            data=json.dumps({'status': 'pending'}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        rows = ActivityLog.objects.filter(category=ActivityLog.Category.ORDER)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows[0].metadata.get('from_status'), 'unpaid')
        self.assertEqual(rows[0].metadata.get('to_status'), 'pending')

    def test_kitchen_invalid_move_logs_nothing(self):
        res = self.client.post(
            reverse('kitchen_display:update_status', args=[self.order.pk]),
            data=json.dumps({'status': 'completed'}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(ActivityLog.objects.count(), 0)

    def test_staff_dashboard_renders_without_context_errors(self):
        # Dashboard 302s to a tokenized URL on first visit, then renders.
        res = self.client.get(reverse('canteen_menu:staff_dashboard'), follow=True)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Activity Log')