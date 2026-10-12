"""Tests for the manual canteen open/close switch.

The switch is read on every request, so these tests care about two things
beyond correctness: that a write is visible immediately (no stale cache), and
that the gate lets the right people through -- staff must never be locked out
of their own dashboard, or nobody could reopen the canteen.
"""

import json

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.models import CustomUser

from .models import SystemStatus
from .system_status import get_status, invalidate, is_accepting_orders, set_open


class SystemStatusServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        invalidate()

    def tearDown(self):
        cache.clear()
        invalidate()

    def test_defaults_to_open_and_creates_the_singleton(self):
        self.assertFalse(SystemStatus.objects.exists())

        status = get_status()

        self.assertTrue(status['is_open'])
        self.assertEqual(SystemStatus.objects.filter(pk=1).count(), 1)

    def test_closing_records_the_reason(self):
        set_open(False, message='Out of rice')

        status = get_status()

        self.assertFalse(status['is_open'])
        self.assertEqual(status['message'], 'Out of rice')
        self.assertFalse(is_accepting_orders())

    def test_reopening_clears_the_reason(self):
        set_open(False, message='Brownout')
        set_open(True)

        status = get_status()

        self.assertTrue(status['is_open'])
        self.assertEqual(status['message'], '')

    def test_a_write_beats_a_warm_cache(self):
        # Warm BOTH cache levels, then flip the switch: the memo must not win.
        self.assertTrue(get_status()['is_open'])

        set_open(False)

        self.assertFalse(get_status()['is_open'])

    def test_repeated_reads_do_not_touch_the_database(self):
        get_status()  # warm

        with self.assertNumQueries(0):
            get_status()
            get_status()

    def test_message_is_truncated_to_the_column_width(self):
        set_open(False, message='x' * 500)

        self.assertEqual(len(get_status()['message']), 200)


class SystemGateMiddlewareTests(TestCase):
    def setUp(self):
        cache.clear()
        invalidate()

    def tearDown(self):
        cache.clear()
        invalidate()

    def test_kiosk_welcome_loads_when_open(self):
        self.assertEqual(self.client.get('/kiosk/').status_code, 200)

    def test_kiosk_welcome_redirects_to_the_notice_when_closed(self):
        set_open(False, message='Maintenance')

        response = self.client.get('/kiosk/')

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('core_app:system_closed'), response['Location'])

    def test_kiosk_menu_still_loads_when_closed(self):
        # A walk-in holding an unpaid queue slip must still be able to read it.
        set_open(False)

        self.assertEqual(self.client.get('/kiosk/menu/').status_code, 200)

    def test_menu_renders_the_closed_overlay_when_closed(self):
        set_open(False, message='Closed for cleaning')

        response = self.client.get('/kiosk/menu/')

        self.assertContains(response, 'system-closed-overlay')
        self.assertContains(response, 'Closed for cleaning')

    def test_checkout_is_refused_when_closed(self):
        set_open(False, message='Maintenance')

        response = self.client.post(
            '/kiosk/api/checkout/',
            data=json.dumps({'cart': [{'id': 1, 'qty': 1}]}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 423)
        self.assertFalse(response.json()['success'])
        self.assertTrue(response.json()['system_closed'])

    def test_process_checkout_view_also_refuses(self):
        """Defence in depth: the view's own gate, independent of middleware."""
        from customer_portal.views import process_checkout

        set_open(False, message='Out of stock')

        request = RequestFactory().post(
            '/kiosk/api/checkout/',
            data=json.dumps({'cart': []}),
            content_type='application/json',
        )
        request.user = AnonymousUser()

        response = process_checkout(request)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(json.loads(response.content)['message'], 'Out of stock')

    def test_staff_keep_full_access_while_closed(self):
        set_open(False)
        staff = CustomUser.objects.create_user(
            username='staff-gate', password='pw', role='STAFF')
        self.client.force_login(staff)

        self.assertEqual(self.client.get('/kiosk/').status_code, 200)

    def test_status_api_is_never_gated(self):
        set_open(False, message='Maintenance')

        response = self.client.get(reverse('core_app:system_status_api'))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['is_open'])


class SystemToggleApiTests(TestCase):
    def setUp(self):
        cache.clear()
        invalidate()
        self.url = reverse('core_app:system_toggle_api')

    def tearDown(self):
        cache.clear()
        invalidate()

    def _post(self, payload, **extra):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            **extra,
        )

    def test_anonymous_is_rejected(self):
        self.assertEqual(self._post({'is_open': False}).status_code, 401)

    def test_student_cannot_flip_the_switch(self):
        student = CustomUser.objects.create_user(
            username='stud-toggle', password='pw', role='STUDENT')
        self.client.force_login(student)

        self.assertEqual(self._post({'is_open': False}).status_code, 403)
        self.assertTrue(get_status()['is_open'])

    def test_staff_can_close_with_a_reason(self):
        staff = CustomUser.objects.create_user(
            username='staff-toggle', password='pw', role='STAFF')
        self.client.force_login(staff)

        response = self._post({'is_open': False, 'message': 'Lunch break'})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['is_open'])
        self.assertFalse(get_status()['is_open'])
        row = SystemStatus.objects.get(pk=1)
        self.assertEqual(row.message, 'Lunch break')
        self.assertEqual(row.updated_by, staff)

    def test_staff_can_reopen(self):
        staff = CustomUser.objects.create_user(
            username='staff-reopen', password='pw', role='STAFF')
        self.client.force_login(staff)
        self._post({'is_open': False, 'message': 'Lunch break'})

        response = self._post({'is_open': True})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['is_open'])
        self.assertTrue(get_status()['is_open'])
        self.assertEqual(SystemStatus.objects.get(pk=1).message, '')

    def test_omitting_is_open_toggles(self):
        staff = CustomUser.objects.create_user(
            username='staff-toggle2', password='pw', role='STAFF')
        self.client.force_login(staff)

        self.assertFalse(self._post({}).json()['is_open'])
        self.assertTrue(self._post({}).json()['is_open'])

    def test_toggle_is_written_to_the_activity_log(self):
        from activity_log.models import ActivityLog

        staff = CustomUser.objects.create_user(
            username='staff-log', password='pw', role='STAFF')
        self.client.force_login(staff)

        self._post({'is_open': False, 'message': 'Closing early'})

        self.assertTrue(
            ActivityLog.objects.filter(action__icontains='Closed the canteen').exists()
        )


class SystemStatusApiTests(TestCase):
    def setUp(self):
        cache.clear()
        invalidate()

    def tearDown(self):
        cache.clear()
        invalidate()

    def test_reports_open_by_default(self):
        response = self.client.get(reverse('core_app:system_status_api'))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['is_open'])
        self.assertTrue(body['accepting_orders'])
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_reports_closed_with_the_reason(self):
        set_open(False, message='No stock left')

        body = self.client.get(reverse('core_app:system_status_api')).json()

        self.assertFalse(body['is_open'])
        self.assertFalse(body['accepting_orders'])
        self.assertEqual(body['message'], 'No stock left')

    def test_repeated_polls_are_database_free(self):
        self.client.get(reverse('core_app:system_status_api'))  # warm the cache

        with self.assertNumQueries(0):
            self.client.get(reverse('core_app:system_status_api'))


class SystemClosedPageTests(TestCase):
    def setUp(self):
        cache.clear()
        invalidate()

    def tearDown(self):
        cache.clear()
        invalidate()

    def test_page_shows_the_reason_and_is_uncached(self):
        set_open(False, message='Back at 3 PM')

        response = self.client.get(reverse('core_app:system_closed'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Back at 3 PM')
        self.assertContains(response, 'Currently Closed')
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_page_renders_without_a_reason(self):
        set_open(False)

        self.assertEqual(
            self.client.get(reverse('core_app:system_closed')).status_code, 200)


class SystemStatusContextTests(TestCase):
    def setUp(self):
        cache.clear()
        invalidate()

    def tearDown(self):
        cache.clear()
        invalidate()

    def test_context_exposes_the_closed_state(self):
        set_open(False, message='Closed for cleaning')

        response = self.client.get('/kiosk/menu/')

        self.assertFalse(response.context['SYSTEM_IS_OPEN'])
        self.assertEqual(response.context['SYSTEM_CLOSED_MESSAGE'], 'Closed for cleaning')

    def test_context_exposes_the_open_state(self):
        response = self.client.get('/kiosk/menu/')

        self.assertTrue(response.context['SYSTEM_IS_OPEN'])
        self.assertTrue(response.context['ACCEPTING_ORDERS'])


class DashboardSwitchTests(TestCase):
    """The control has to be on every dashboard staff actually land on."""

    def setUp(self):
        cache.clear()
        invalidate()
        self.staff = CustomUser.objects.create_user(
            username='staff-dash', password='pw', role='STAFF')
        self.client.force_login(self.staff)

    def tearDown(self):
        cache.clear()
        invalidate()

    def test_unified_staff_dashboard_shows_the_switch(self):
        # The dashboard redirects to its tokenised URL on first hit.
        response = self.client.get('/canteen/dashboard/', follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/core/system/toggle/')

    def test_kitchen_staff_dashboard_shows_the_switch(self):
        response = self.client.get('/kitchen/dashboard/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/core/system/toggle/')

    def test_admin_governance_shows_the_switch(self):
        from django.utils import timezone

        session = self.client.session
        session['admin_verified'] = True
        session['admin_verified_at'] = timezone.now().timestamp()
        session.save()

        response = self.client.get('/kitchen/admin-control/governance/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/core/system/toggle/')
