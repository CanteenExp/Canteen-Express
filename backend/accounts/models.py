import random
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('STUDENT', 'Student'),
        ('FACULTY', 'Faculty'),
        ('STAFF', 'Canteen Staff'),
        ('DELIVERY', 'Delivery Personnel'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='STUDENT')
    is_email_verified = models.BooleanField(default=False)
    phone = models.CharField(max_length=20, blank=True, null=True)
    vehicle_plate = models.CharField(max_length=50, blank=True, null=True)
    is_available = models.BooleanField(default=True)
    availability_updated_at = models.DateTimeField(blank=True, null=True)
    account_status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('restricted', 'Restricted'),
            ('banned', 'Banned'),
            ('held', 'Held'),
            ('penalized', 'Penalized'),
        ],
        default='active'
    )

    # Rider availability
    is_available = models.BooleanField(default=True)
    availability_updated_at = models.DateTimeField(blank=True, null=True)
    
    # OTP Fields
    otp_code = models.CharField(max_length=6, blank=True, null=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)

    def generate_otp(self):
        code = str(random.randint(100000, 999999))
        self.otp_code = code
        self.otp_created_at = timezone.now()
        self.save()
        return code

    def is_otp_valid(self, input_code):
        # OTP is valid for 10 minutes
        if self.otp_code == input_code and self.otp_created_at:
            expiry_time = self.otp_created_at + timedelta(minutes=10)
            return timezone.now() <= expiry_time
        return False
