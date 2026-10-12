from django.conf import settings
from django.db import models


class SystemStatus(models.Model):
    """Singleton row (always pk=1) holding the manual "canteen is open" switch.

    Staff flip this from their dashboard to stop taking orders right now -- out
    of stock, lunch break, brownout, maintenance -- without touching operating
    hours or redeploying anything.

    This value is consulted on *every* request (middleware + context processor),
    so it is never read with a query in the hot path. core_app.system_status
    serves it from the shared cache; this table is only the durable source of
    truth that cache is rebuilt from.
    """

    is_open = models.BooleanField(
        default=True,
        help_text='Uncheck to stop accepting new orders from customers.',
    )
    message = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text='Optional note shown to customers, e.g. "Out of rice, back at 3 PM".',
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    reopened_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        help_text='Staff member who last flipped the switch.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'System status'
        verbose_name_plural = 'System status'

    def __str__(self):
        if self.is_open:
            return 'Canteen is OPEN'
        return f'Canteen is CLOSED ({self.message})' if self.message else 'Canteen is CLOSED'
