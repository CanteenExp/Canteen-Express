from django.db import models
from django.conf import settings

class Order(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PREPARING', 'Preparing'),
        ('READY', 'Ready for Pickup'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )

    # Nullable FK: Populated if Faculty/Staff orders, None if Kiosk Student orders
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='orders'
    )
    
    # Fields specifically for Kiosk Guest Orders
    student_name = models.CharField(max_length=100, blank=True, null=True, help_text="Used for Kiosk orders")
    student_id_number = models.CharField(max_length=20, blank=True, null=True, help_text="Optional School ID for verification")

    # Queue & Order Metadata
    queue_number = models.IntegerField(unique=True, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        name = self.student_name or (self.customer.get_full_name() if self.customer else "Guest")
        return f"Order #{self.id} (Queue {self.queue_number}) - {name}"