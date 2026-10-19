"""Tests for the manual canteen open/close switch.

The switch is read on every request, so these tests care about two things
beyond correctness: that a write is visible immediately (no stale cache), and
that the gate lets the right people through -- staff must never be locked out
of their own dashboard, or nobody could reopen the canteen.
"""

import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser

from .closure_reasons import CLOSURE_REASONS, label_for, resolve_message
from .models import SystemStatus
from .system_status import (
    MODE_AUTO,
    MODE_FORCE_CLOSED,
    MODE_FORCE_OPEN,
    VALID_MODES,
    get_status,
    invalidate,
    is_accepting_orders,
    is_open,
    resolve_status,
    set_mode,
    set_open,
)
from core_app import utils as core_utils


def weekday_at(hour, minute=0, weekday=None):
    """An aware datetime on a weekday at the given time, for driving the clock.

    Tests must never depend on when they run: the suite passes an explicit
    moment to the timetable instead of hoping CI is open for business.
    """
    moment = timezone.localtime()
    if weekday is None:
        weekday = 0
        while moment.weekday() > 4:
            moment += timedelta(days=1)
    else:
        moment += timedelta(days=(weekday - moment.weekday()) % 7)
    return moment.replace(hour=hour, minute=minute, second=0, microsecond=0)


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

    def test_dashboard_renders_the_three_way_control(self):
        response = self.client.get('/kitchen/dashboard/')

        self.assertContains(response, 'Automatic')
        self.assertContains(response, 'Open now')
        self.assertContains(response, 'Closing reason')
        # Every preset must be pickable so staff never have to type.
        self.assertContains(response, 'value="END_OF_DAY"')

    def test_dashboards_render_their_javascript(self):
        """The control is inline JS, so a template syntax error would break it."""
        for url in ('/kitchen/dashboard/', '/canteen/dashboard/'):
            with self.subTest(url=url):
                response = self.client.get(url, follow=True)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "apply('FORCE_OPEN')")


class OperatingHoursScheduleTests(SimpleTestCase):
    """The timetable itself. It drives the clock explicitly, never the wall clock."""

    def test_open_inside_the_window(self):
        self.assertTrue(core_utils.is_operating_hours(weekday_at(8)))
        self.assertTrue(core_utils.is_operating_hours(weekday_at(12)))
        self.assertTrue(core_utils.is_operating_hours(weekday_at(16, 59)))

    def test_closed_outside_the_window(self):
        self.assertFalse(core_utils.is_operating_hours(weekday_at(7, 59)))
        self.assertFalse(core_utils.is_operating_hours(weekday_at(17)))  # 5:00 PM sharp
        self.assertFalse(core_utils.is_operating_hours(weekday_at(22)))

    def test_closed_all_weekend(self):
        self.assertFalse(core_utils.is_operating_hours(weekday_at(12, weekday=5)))
        self.assertFalse(core_utils.is_operating_hours(weekday_at(12, weekday=6)))

    def test_the_window_is_described_in_words(self):
        self.assertEqual(
            core_utils.operating_hours_text(), 'Monday to Friday, 8:00 AM to 5:00 PM')

    def test_next_opening_later_today(self):
        self.assertEqual(core_utils.next_opening_text(weekday_at(6)), 'today at 8:00 AM')

    def test_next_opening_tomorrow_from_a_midweek_evening(self):
        self.assertEqual(
            core_utils.next_opening_text(weekday_at(18, weekday=0)),
            'tomorrow at 8:00 AM')

    def test_next_opening_from_friday_evening_is_monday(self):
        self.assertEqual(
            core_utils.next_opening_text(weekday_at(18, weekday=4)),
            'on Monday at 8:00 AM')

    def test_schedule_message_names_the_hours_and_the_reopening(self):
        message = core_utils.schedule_closed_message(weekday_at(18, weekday=0))

        self.assertIn('Monday to Friday, 8:00 AM to 5:00 PM', message)
        self.assertIn('tomorrow at 8:00 AM', message)

    def test_the_kill_switch_disables_the_window(self):
        with self.settings(ENFORCE_OPERATING_HOURS=False):
            self.assertTrue(core_utils.is_operating_hours())


class SystemModeTests(TestCase):
    """AUTO follows the timetable; FORCE_* override it. This is the whole point."""

    def setUp(self):
        cache.clear()
        invalidate()

    def tearDown(self):
        cache.clear()
        invalidate()

    def _raw(self, **overrides):
        raw = {'mode': MODE_AUTO, 'message': '', 'reason_code': ''}
        raw.update(overrides)
        return raw

    def test_a_fresh_install_runs_on_the_schedule(self):
        self.assertEqual(get_status()['mode'], MODE_AUTO)
        self.assertFalse(get_status()['is_override'])

    def test_auto_is_open_inside_the_window(self):
        status = resolve_status(self._raw(), now=weekday_at(10))

        self.assertTrue(status['is_open'])
        self.assertEqual(status['message'], '')
        self.assertTrue(status['schedule_open'])

    def test_auto_is_closed_outside_the_window_with_the_schedule_message(self):
        status = resolve_status(self._raw(), now=weekday_at(19))

        self.assertFalse(status['is_open'])
        self.assertEqual(status['reason_code'], 'OPERATING_HOURS')
        self.assertEqual(status['reason_label'], 'Outside operating hours')
        self.assertIn('Monday to Friday', status['message'])
        self.assertFalse(status['is_override'])

    def test_the_timetable_is_not_frozen_by_the_cached_row(self):
        raw = self._raw()

        self.assertTrue(resolve_status(raw, now=weekday_at(10))['is_open'])
        self.assertFalse(resolve_status(raw, now=weekday_at(19))['is_open'])

    def test_the_schedule_closes_ordering_when_the_clock_says_so(self):
        with patch('core_app.utils.is_operating_hours', return_value=False):
            self.assertFalse(is_open())
            self.assertFalse(is_accepting_orders())

    def test_force_open_extends_past_closing_time(self):
        set_mode(MODE_FORCE_OPEN)

        with patch('core_app.utils.is_operating_hours', return_value=False):
            self.assertTrue(is_open())
            self.assertTrue(is_accepting_orders())

    def test_force_closed_wins_over_an_open_timetable(self):
        set_mode(MODE_FORCE_CLOSED, reason_code='BREAK')

        with patch('core_app.utils.is_operating_hours', return_value=True):
            self.assertFalse(is_open())
            self.assertFalse(is_accepting_orders())

    def test_returning_to_auto_clears_the_override(self):
        set_mode(MODE_FORCE_CLOSED, reason_code='BREAK')

        status = set_mode(MODE_AUTO)

        self.assertEqual(status['mode'], MODE_AUTO)
        row = SystemStatus.objects.get(pk=1)
        self.assertEqual(row.message, '')
        self.assertEqual(row.reason_code, '')

    def test_a_preset_reason_supplies_the_customer_message(self):
        set_mode(MODE_FORCE_CLOSED, reason_code='END_OF_DAY')

        row = SystemStatus.objects.get(pk=1)
        self.assertEqual(row.message, resolve_message('END_OF_DAY'))
        self.assertIn('8:00 AM', row.message)

    def test_other_uses_the_typed_message(self):
        set_mode(MODE_FORCE_CLOSED, reason_code='OTHER', message='Brownout po')

        self.assertEqual(SystemStatus.objects.get(pk=1).message, 'Brownout po')

    def test_a_closure_with_no_reason_still_tells_the_customer_something(self):
        set_mode(MODE_FORCE_CLOSED)

        self.assertTrue(get_status()['message'])

    def test_mode_constants_match_the_model_choices(self):
        codes = [code for code, _label in SystemStatus.MODE_CHOICES]

        self.assertEqual(codes, list(VALID_MODES))

    def test_reads_stay_database_free(self):
        get_status()  # warm

        with self.assertNumQueries(0):
            get_status()
            get_status()


class SystemModeApiTests(TestCase):
    """The dashboard control talks to this endpoint; keep it forgiving."""

    def setUp(self):
        cache.clear()
        invalidate()
        self.url = reverse('core_app:system_toggle_api')
        self.staff = CustomUser.objects.create_user(
            username='staff-mode', password='pw', role='STAFF')
        self.client.force_login(self.staff)

    def tearDown(self):
        cache.clear()
        invalidate()

    def _post(self, payload):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

    def test_staff_can_extend_the_day(self):
        body = self._post({'mode': MODE_FORCE_OPEN}).json()

        self.assertTrue(body['is_open'])
        self.assertEqual(body['mode'], MODE_FORCE_OPEN)
        self.assertIn('OPEN', body['notice'])

    def test_staff_can_close_with_a_preset_reason(self):
        body = self._post(
            {'mode': MODE_FORCE_CLOSED, 'reason_code': 'OUT_OF_STOCK'}).json()

        self.assertFalse(body['is_open'])
        self.assertEqual(body['reason_label'], 'Out of stock for today')
        self.assertIn('run out of ingredients', body['message'])

    def test_staff_can_go_back_to_the_automatic_schedule(self):
        self._post({'mode': MODE_FORCE_CLOSED, 'reason_code': 'BREAK'})

        body = self._post({'mode': MODE_AUTO}).json()

        self.assertEqual(body['mode'], MODE_AUTO)
        self.assertEqual(body['message'], '')
        self.assertEqual(SystemStatus.objects.get(pk=1).mode, MODE_AUTO)

    def test_an_unknown_mode_is_rejected_without_changing_anything(self):
        response = self._post({'mode': 'PANIC'})

        self.assertEqual(response.status_code, 400)
        # Rejected before any write: not even the singleton row is created.
        self.assertFalse(SystemStatus.objects.exists())

    def test_the_old_is_open_payload_still_works(self):
        body = self._post({'is_open': False, 'message': 'Lunch break'}).json()

        self.assertFalse(body['is_open'])
        self.assertEqual(body['mode'], MODE_FORCE_CLOSED)
        self.assertEqual(body['message'], 'Lunch break')

    def test_students_still_cannot_use_the_new_payload(self):
        student = CustomUser.objects.create_user(
            username='stud-mode', password='pw', role='STUDENT')
        self.client.force_login(student)

        self.assertEqual(self._post({'mode': MODE_FORCE_OPEN}).status_code, 403)

    def test_switching_to_auto_is_logged(self):
        from activity_log.models import ActivityLog

        self._post({'mode': MODE_AUTO})

        self.assertTrue(
            ActivityLog.objects.filter(action__icontains='automatic schedule').exists())


class ScheduleGateTests(TestCase):
    """Outside hours the canteen is closed on its own, gate included."""

    def setUp(self):
        cache.clear()
        invalidate()

    def tearDown(self):
        cache.clear()
        invalidate()

    @patch('core_app.utils.is_operating_hours', return_value=False)
    def test_the_status_feed_explains_the_schedule(self, _hours):
        body = self.client.get(reverse('core_app:system_status_api')).json()

        self.assertFalse(body['is_open'])
        self.assertFalse(body['accepting_orders'])
        self.assertEqual(body['reason_code'], 'OPERATING_HOURS')
        self.assertIn('Monday to Friday', body['message'])
        self.assertEqual(body['mode'], MODE_AUTO)

    @patch('core_app.utils.is_operating_hours', return_value=False)
    def test_customers_are_sent_to_the_notice_outside_hours(self, _hours):
        response = self.client.get('/kiosk/')

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('core_app:system_closed'), response['Location'])

    @patch('core_app.utils.is_operating_hours', return_value=False)
    def test_the_notice_mentions_when_ordering_resumes(self, _hours):
        response = self.client.get(reverse('core_app:system_closed'))

        self.assertContains(response, 'Outside Our Operating Hours')

    @patch('core_app.utils.is_operating_hours', return_value=False)
    def test_staff_reach_the_kiosk_outside_hours(self, _hours):
        staff = CustomUser.objects.create_user(
            username='staff-hours', password='pw', role='STAFF')
        self.client.force_login(staff)

        self.assertEqual(self.client.get('/kiosk/').status_code, 200)

    @patch('core_app.utils.is_operating_hours', return_value=False)
    def test_checkout_is_refused_outside_hours(self, _hours):
        response = self.client.post(
            '/kiosk/api/checkout/',
            data=json.dumps({'cart': [{'id': 1, 'qty': 1}]}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 423)
        self.assertTrue(response.json()['system_closed'])


class ClosureReasonPresetTests(SimpleTestCase):
    """Whatever staff pick is what customers read: keep the list publishable."""

    def test_every_selectable_reason_has_a_customer_message(self):
        for reason in CLOSURE_REASONS:
            if reason['code'] == 'OTHER':
                continue
            with self.subTest(code=reason['code']):
                self.assertTrue(reason['message'].strip())
                self.assertLessEqual(len(reason['message']), 200)

    def test_reason_codes_are_unique(self):
        codes = [reason['code'] for reason in CLOSURE_REASONS]

        self.assertEqual(len(codes), len(set(codes)))

    def test_the_schedule_reason_is_not_selectable(self):
        self.assertNotIn('OPERATING_HOURS', [r['code'] for r in CLOSURE_REASONS])
        self.assertEqual(label_for('OPERATING_HOURS'), 'Outside operating hours')

    def test_a_preset_message_cannot_be_overridden_by_a_typed_note(self):
        self.assertEqual(resolve_message('BREAK', 'ignore me'), resolve_message('BREAK'))

    def test_an_empty_choice_still_yields_a_message(self):
        self.assertTrue(resolve_message('', '').strip())
