from django.db import models
from django.conf import settings
from order_management.models import Order

class DeliveryRequest(models.Model):
    class RequestStatus(models.TextChoices):
        SEARCHING = 'SEARCHING', 'Searching for Rider'
        ACCEPTED = 'ACCEPTED', 'Rider Accepted'
        REJECTED = 'REJECTED', 'Rejected'
        TIMEOUT = 'TIMEOUT', 'No Rider Available (5-Min Timeout)'

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery_info')
    rider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        limit_choices_to={'role': 'RIDER'},
        related_name='deliveries'
    )
    delivery_location = models.CharField(max_length=255, help_text="Building & Room Number")
    status = models.CharField(max_length=20, choices=RequestStatus.choices, default=RequestStatus.SEARCHING)
    requested_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)