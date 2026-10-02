from django.test import TestCase, Client
from django.urls import reverse
from django.core.management import call_command
from accounts.models import CustomUser
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
