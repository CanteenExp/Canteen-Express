from django.db import models
from django.conf import settings
from customer_portal.models import Order

class DeliveryRequest(models.Model):
    class RequestStatus(models.TextChoices):
        SEARCHING = 'SEARCHING', 'Searching for Rider'
        ACCEPTED = 'ACCEPTED', 'Rider Accepted'
        DELIVERED = 'DELIVERED', 'Delivered'
        REJECTED = 'REJECTED', 'Rejected'
        TIMEOUT = 'TIMEOUT', 'No Rider Available (5-Min Timeout)'

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery_info')
    rider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='deliveries'
    )
    delivery_location = models.CharField(max_length=255, help_text="Building & Room Number")
    status = models.CharField(max_length=20, choices=RequestStatus.choices, default=RequestStatus.SEARCHING)
    requested_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    rider_lat = models.FloatField(null=True, blank=True)
    rider_lng = models.FloatField(null=True, blank=True)
    dest_lat = models.FloatField(null=True, blank=True)
    dest_lng = models.FloatField(null=True, blank=True)
    location_updated_at = models.DateTimeField(null=True, blank=True)

class DeliveryMessage(models.Model):
    delivery = models.ForeignKey(DeliveryRequest, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender.username}: {self.message[:30]}"
