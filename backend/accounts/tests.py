import time
from django.test import TestCase, Client
from django.core.cache import cache
from django.core.management import call_command
from django.urls import reverse
from accounts.models import CustomUser
from customer_portal.models import Order
from activity_log.models import ActivityLog
from accounts.views import LOGIN_FAIL_LIMIT, LOGIN_LOCK_SECONDS, _login_lock_remaining

class ResetFacultyDataCommandTestCase(TestCase):
    def test_reset_faculty_data(self):
        # Create faculty and student users
        faculty = CustomUser.objects.create_user(
            username='faculty1',
            email='faculty1@psu.palawan.edu.ph',
            password='password123',
            role='FACULTY',
            loyalty_points=250.00
        )
        student = CustomUser.objects.create_user(
            username='student1',
            email='student1@example.com',
            password='password123',
            role='STUDENT',
            loyalty_points=100.00
        )

        # Create orders for faculty and student
        faculty_order = Order.objects.create(
            order_number='FAC001',
            customer=faculty,
            total_amount=150.00,
            status='completed'
        )
        student_order = Order.objects.create(
            order_number='STU001',
            customer=student,
            total_amount=100.00,
            status='completed'
        )

        # Create activity log
        ActivityLog.objects.create(
            action='Test Action',
            actor=faculty
        )

        # Run management command
        call_command('reset_faculty_data')

        # Assertions
        # Faculty order should be deleted
        self.assertFalse(Order.objects.filter(id=faculty_order.id).exists())
        # Student order should remain
        self.assertTrue(Order.objects.filter(id=student_order.id).exists())

        # Faculty points should be 0.00
        faculty.refresh_from_db()
        self.assertEqual(float(faculty.loyalty_points), 0.00)

        # Student points should remain 100.00
        student.refresh_from_db()
        self.assertEqual(float(student.loyalty_points), 100.00)

        # Activity log should be empty
        self.assertEqual(ActivityLog.objects.count(), 0)


class LoginLockoutTests(TestCase):
    """The password throttle locks for 60s and the form counts it down."""

    def setUp(self):
        cache.clear()
        self.client = Client()
        CustomUser.objects.create_user(
            username='lock_staff', password='correctpass', role='STAFF'
        )
        self.url = reverse('accounts:staff_login')

    def tearDown(self):
        cache.clear()

    def _fail(self, times):
        for _ in range(times):
            self.client.post(self.url, {
                'username': 'lock_staff', 'password': 'wrongpass'
})

    def test_lockout_is_sixty_seconds_not_fifteen_minutes(self):
        self.assertEqual(LOGIN_LOCK_SECONDS, 60)
        self.assertEqual(LOGIN_FAIL_LIMIT, 5)

    def _lock_key(self, key='staff', ip='127.0.0.1'):
        return f'login_lock_{key}_{ip}'

    def _fail_key(self, key='staff', ip='127.0.0.1'):
        return f'login_fail_{key}_{ip}'

    def test_four_failures_do_not_lock(self):
        self._fail(4)
        self.assertIsNone(cache.get(self._lock_key()))
        response = self.client.post(self.url, {
            'username': 'lock_staff', 'password': 'correctpass'
        })
        self.assertEqual(response.status_code, 302)

    def test_fifth_failure_locks_and_shows_countdown(self):
        self._fail(LOGIN_FAIL_LIMIT)
        response = self.client.post(self.url, {
            'username': 'lock_staff', 'password': 'correctpass'
        })
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('Too many failed attempts', html)
        self.assertIn('Retry available in', html)
        self.assertIn('data-lock-countdown', html)
        # The correct password is rejected while the lock is live.
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_lock_expires_and_login_succeeds(self):
        self._fail(LOGIN_FAIL_LIMIT)
        # Fast-forward past the 60s window instead of sleeping.
        cache.set(self._lock_key(), time.time() - 1, timeout=1)
        response = self.client.post(self.url, {
            'username': 'lock_staff', 'password': 'correctpass'
        })
        self.assertEqual(response.status_code, 302)

    def test_successful_login_clears_the_counter(self):
        self._fail(3)
        self.client.post(self.url, {'username': 'lock_staff', 'password': 'correctpass'})
        self._fail(3)
        # 3 + 3 failures must not add up to a lock once one login succeeded.
        response = self.client.post(self.url, {
            'username': 'lock_staff', 'password': 'correctpass'
        })
        self.assertEqual(response.status_code, 302)

    def test_lockout_is_scoped_per_portal(self):
        self._fail(LOGIN_FAIL_LIMIT)
        # The rider portal shares the campus IP but keeps its own counter.
        CustomUser.objects.create_user(
            username='lock_rider', password='correctpass', role='DELIVERY'
        )
        response = self.client.post(reverse('accounts:delivery_login'), {
            'username': 'lock_rider', 'password': 'correctpass'
        })
        self.assertEqual(response.status_code, 302)
