import random
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class CustomUser(AbstractUser):
    # A rider is only considered truly "online" if their rider dashboard
    # (SSE stream) reported a heartbeat within this window.
    RIDER_ONLINE_TIMEOUT = timedelta(seconds=90)

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
    loyalty_points = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)

    # Rider availability. is_available is the GO/STOP intent; presence also
    # requires a fresh heartbeat (availability_updated_at) -- see
    # is_really_online below. Declared once only: an earlier duplicate pair of
    # these fields shadowed the values above and was silently discarded.
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
    status_reason = models.CharField(max_length=255, blank=True, null=True)

    @property
    def is_really_online(self):
        """True only while the rider's dashboard is actually connected.

        is_available is just the rider's GO/STOP intent; presence additionally
        requires a fresh heartbeat (availability_updated_at) so staff dashboards
        stop showing "Online · Ready" for riders who closed the app."""
        if not self.is_available or self.availability_updated_at is None:
            return False
        return (timezone.now() - self.availability_updated_at) <= self.RIDER_ONLINE_TIMEOUT
