from django.test import TestCase, Client
from django.urls import reverse
from django.core.management import call_command
from django.core.exceptions import ValidationError
import json
import time
from accounts.models import CustomUser
from accounts.validators import MixedCharacterPasswordValidator
from accounts.views import _otp_hash
from customer_portal.models import Order
from activity_log.models import ActivityLog

class DeliveryLoginTestCase(TestCase):
    def test_delivery_login_renders_csrf(self):
        client = Client()
        response = client.get(reverse('accounts:delivery_login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'csrfmiddlewaretoken')
        self.assertNotContains(response, '{% csrf_token %}')

    def test_staff_login_renders_csrf(self):
        client = Client()
        response = client.get(reverse('accounts:staff_login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'csrfmiddlewaretoken')
        self.assertNotContains(response, '{% csrf_token %}')

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


class FacultyDashboardDialogTestCase(TestCase):
    """The cancel / convert dialogs must actually render on the dashboard.

    Template-land only: this guards the reason dropdown, the shared confirmation
    step and the success dialog against a future refactor quietly dropping them.
    """

    def setUp(self):
        self.faculty = CustomUser.objects.create_user(
            username='dlg_faculty', email='dlg@psu.palawan.edu.ph',
            password='password123', role='FACULTY')

    def test_cancel_and_convert_dialogs_render(self):
        self.client.force_login(self.faculty)
        # The dashboard redirects once to a session-token URL, hence follow=True.
        res = self.client.get(reverse('accounts:dashboard'), follow=True)
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        for marker in (
            'id="cancel-reason-select"',
            'id="cancel-reason-other"',
            'toggleFacultyOtherReason()',
            'id="faculty-confirm-modal"',
            'id="faculty-success-modal"',
            'showFacultySuccess(',
            'submitFacultyCancelOrder()',
            'convertFacultyDeliveryToPickup()',
            'Back to Menu',
        ):
            self.assertIn(marker, html)


class FacultyProfileUpdateTestCase(TestCase):
    """The faculty header avatar edits only the signed-in faculty/staff account."""

    def setUp(self):
        self.faculty = CustomUser.objects.create_user(
            username='prof_profile', email='prof_profile@psu.palawan.edu.ph',
            password='password123', role='FACULTY', is_email_verified=True,
            first_name='Faculty One')
        self.url = reverse('accounts:faculty_profile_update')

    def _post(self, payload, client=None):
        return (client or self.client).post(
            self.url, data=json.dumps(payload), content_type='application/json')

    def test_updates_name_department_and_phone(self):
        self.client.force_login(self.faculty)
        res = self._post({
            'name': '  Faculty   Two ',
            'college_department': 'College of Sciences',
            'phone': '0917 123 4567',
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['success'])
        self.faculty.refresh_from_db()
        self.assertEqual(self.faculty.first_name, 'Faculty Two')
        self.assertEqual(self.faculty.last_name, '')
        self.assertEqual(self.faculty.college_department, 'College of Sciences')
        self.assertEqual(self.faculty.phone, '0917 123 4567')
        self.assertEqual(res.json()['display_name'], 'Faculty Two')

    def test_optional_fields_may_be_cleared(self):
        self.faculty.college_department = 'Old Department'
        self.faculty.phone = '09170000000'
        self.faculty.save()
        self.client.force_login(self.faculty)
        res = self._post({'name': 'Faculty One', 'college_department': '', 'phone': ''})
        self.assertEqual(res.status_code, 200)
        self.faculty.refresh_from_db()
        self.assertEqual(self.faculty.college_department, '')
        self.assertEqual(self.faculty.phone, '')

    def test_rejects_invalid_input(self):
        self.client.force_login(self.faculty)
        cases = [
            {'name': ''},
            {'name': 'Faculty 123'},
            {'name': 'Faculty One', 'phone': 'not-a-number'},
            {'name': 'Faculty One', 'college_department': 'x' * 121},
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                res = self._post(payload)
                self.assertEqual(res.status_code, 400)
                self.assertFalse(res.json()['success'])
        self.faculty.refresh_from_db()
        self.assertEqual(self.faculty.first_name, 'Faculty One')

    def test_blocks_students_and_anonymous_users(self):
        student = CustomUser.objects.create_user(
            username='student_profile', email='student_profile@example.com',
            password='password123', role='STUDENT')
        self.client.force_login(student)
        self.assertEqual(self._post({'name': 'Student One'}).status_code, 403)
        student.refresh_from_db()
        self.assertEqual(student.first_name, '')

        anon = Client()
        self.assertEqual(self._post({'name': 'Nobody'}, client=anon).status_code, 401)

    def test_header_shows_account_avatar_instead_of_logo(self):
        self.client.force_login(self.faculty)
        html = self.client.get(reverse('accounts:dashboard'), follow=True).content.decode()
        self.assertIn('id="faculty-header-avatar"', html)
        self.assertIn('openAccountModal()', html)
        self.assertIn('id="account-modal"', html)
        self.assertIn('id="profile-name-input"', html)
        self.assertIn('id="profile-department-input"', html)
        self.assertIn('value="Faculty One"', html)
        self.assertIn('VERIFIED', html.upper())
        self.assertNotIn('alt="Logo"', html)

    def test_existing_split_name_is_shown_and_preserved(self):
        self.faculty.first_name = 'Faculty'
        self.faculty.last_name = 'One'
        self.faculty.save()
        self.client.force_login(self.faculty)
        html = self.client.get(reverse('accounts:dashboard'), follow=True).content.decode()
        self.assertIn('value="Faculty One"', html)
        res = self._post({'name': 'Faculty One'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['display_name'], 'Faculty One')
        self.faculty.refresh_from_db()
        self.assertEqual(self.faculty.get_full_name(), 'Faculty One')

class PasswordPolicyTestCase(TestCase):
    """Mixed-character policy is enforced in the app and covered by tests."""

    def test_accepts_a_mixed_character_password(self):
        # Should not raise.
        MixedCharacterPasswordValidator().validate('Str0ng!Pass')

    def test_rejects_each_missing_character_class(self):
        cases = {
            'lowercaseonly1!': 'uppercase letter',
            'UPPERCASEONLY1!': 'lowercase letter',
            'NoNumbersHere!': 'a number',
            'NoSpecial12345': 'a special character',
        }
        for password, expected in cases.items():
            with self.subTest(password=password):
                with self.assertRaises(ValidationError) as ctx:
                    MixedCharacterPasswordValidator().validate(password)
                self.assertIn(expected, str(ctx.exception))

    def test_validate_password_uses_the_project_policy(self):
        from django.contrib.auth.password_validation import validate_password
        with self.assertRaises(ValidationError):
            validate_password('lowercaseonly1!')
        with self.assertRaises(ValidationError):
            validate_password('Sh0rt!')
        # A fully mixed password must pass the whole configured stack.
        validate_password('Str0ng!Pass')


class PasswordResetPolicyTestCase(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='reset_user',
            email='reset_user@psu.palawan.edu.ph',
            password='OldPass1!',
            role='FACULTY',
            is_email_verified=True,
        )
        self.url = reverse('accounts:reset_password_confirm')

    def _arm_reset_session(self, otp='123456'):
        session = self.client.session
        session['reset_otp'] = _otp_hash(otp)
        session['reset_email'] = self.user.email
        session['reset_otp_verified'] = False
        session['reset_otp_created_at'] = int(time.time())
        session['reset_otp_attempts'] = 0
        session.save()

    def _post(self, new_password, otp='123456'):
        return self.client.post(
            self.url,
            data=json.dumps({
                'email': self.user.email,
                'otp': otp,
                'new_password': new_password,
            }),
            content_type='application/json',
        )

    def test_weak_password_is_rejected_and_not_saved(self):
        self._arm_reset_session()
        res = self._post('lowercaseonly1!')
        self.assertEqual(res.status_code, 400)
        self.assertIn('uppercase', res.json()['error'])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('OldPass1!'))

    def test_mixed_password_resets_and_clears_reset_state(self):
        self._arm_reset_session()
        res = self._post('FreshPass2@')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['success'])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('FreshPass2@'))
        for key in ('reset_otp', 'reset_email', 'reset_otp_verified',
                    'reset_otp_created_at', 'reset_otp_attempts'):
            self.assertNotIn(key, self.client.session)

    def test_cannot_reuse_the_current_password(self):
        self._arm_reset_session()
        res = self._post('OldPass1!')
        self.assertEqual(res.status_code, 400)
        self.assertIn('different', res.json()['error'])


class ChangePasswordPolicyTestCase(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='change_user',
            email='change_user@psu.palawan.edu.ph',
            password='OldPass1!',
            role='STAFF',
        )
        self.client.force_login(self.user)
        self.url = reverse('accounts:change_password')

    def _post(self, new_password, confirm=None, current='OldPass1!'):
        return self.client.post(
            self.url,
            data=json.dumps({
                'current_password': current,
                'new_password': new_password,
                'confirm_password': confirm if confirm is not None else new_password,
            }),
            content_type='application/json',
        )

    def test_weak_password_is_rejected(self):
        res = self._post('alllowercase1!')
        self.assertEqual(res.status_code, 400)
        self.assertIn('uppercase', res.json()['error'])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('OldPass1!'))

    def test_mixed_password_is_accepted(self):
        res = self._post('FreshPass2@')
        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('FreshPass2@'))

    def test_cannot_reuse_the_current_password(self):
        res = self._post('OldPass1!')
        self.assertEqual(res.status_code, 400)
        self.assertIn('different', res.json()['error'])

class FacultySignupPasswordPolicyTestCase(TestCase):
    """Faculty signup is one of the password-setting paths under the policy."""

    def setUp(self):
        self.url = reverse('accounts:faculty_auth')
        self.email = 'newprof@psu.palawan.edu.ph'

    def _post(self, password):
        session = self.client.session
        session['otp_verified'] = True
        session['signup_email'] = self.email
        session.save()
        return self.client.post(self.url, {
            'action': 'signup',
            'email': self.email,
            'name': 'New Prof',
            'password': password,
            'confirm_password': password,
        })

    def test_weak_password_shows_policy_error_without_creating_account(self):
        res = self._post('lowercaseonly1!')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'uppercase')
        self.assertFalse(CustomUser.objects.filter(email=self.email).exists())

    def test_mixed_password_creates_the_account(self):
        res = self._post('Str0ng!Pass')
        self.assertEqual(res.status_code, 302)
        self.assertTrue(CustomUser.objects.filter(email=self.email).exists())
