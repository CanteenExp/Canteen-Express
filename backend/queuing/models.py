import uuid
from django.db import models
from customer_portal.models import Order

class DigitalQueueSlip(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='queue_slip')
    queue_number = models.CharField(max_length=20, unique=True)
    qr_code_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Slip #{self.queue_number} - Order {self.order.order_number}"