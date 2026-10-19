from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    """Append-only record of who did what, for the canteen staff Activity Log.

    Deliberately NOT a soft-delete model: a log row that can be hidden is not an
    audit trail. There is no is_active/deleted flag by design.
    """

    class Category(models.TextChoices):
        ORDER = 'ORDER', 'Orders'
        MENU = 'MENU', 'Menu & Stock'
        PAYMENT = 'PAYMENT', 'Payments'
        USER = 'USER', 'User Management'
        DELIVERY = 'DELIVERY', 'Deliveries'
        SYSTEM = 'SYSTEM', 'System'

    class Level(models.TextChoices):
        INFO = 'INFO', 'Info'
        SUCCESS = 'SUCCESS', 'Success'
        WARNING = 'WARNING', 'Warning'
        DANGER = 'DANGER', 'Critical'

    # SET_NULL because deleting a user must not delete their history.
    # related_name='+' keeps CustomUser's namespace clean -- it is already
    # crowded with portal_orders, deliveries, assigned_deliveries, etc.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )

    # Snapshot of the actor's name at write time. If the user is later renamed or
    # deleted, the log must still read correctly -- that is the whole point of
    # an audit trail. Falls back to 'System' for entries with no human actor.
    actor_label = models.CharField(max_length=150, blank=True, default='System')

    category = models.CharField(
        max_length=20, choices=Category.choices, db_index=True)
    level = models.CharField(
        max_length=10, choices=Level.choices, default=Level.INFO, db_index=True)

    # Human-readable sentence, e.g. "Changed Adobo price from 120.00 to 135.00".
    # Written by the caller because only the caller knows the before/after.
    action = models.CharField(max_length=255)

    # Optional short subject the row refers to, e.g. "Order #0042" or "Adobo".
    target = models.CharField(max_length=200, blank=True, default='')

    # Free-form structured detail (old/new values, order ids, reason codes).
    # JSONField is supported on both PostgreSQL and the SQLite fallback.
    metadata = models.JSONField(default=dict, blank=True)

    # Set for entries triggered by a guest / walk-in with no account.
    is_guest = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Activity Log Entry'
        verbose_name_plural = 'Activity Log Entries'
        indexes = [
            models.Index(fields=['-created_at'], name='activity_log_recent_idx'),
            models.Index(fields=['category', '-created_at'],
                         name='activity_log_cat_time_idx'),
        ]

    def __str__(self):
        return f'{self.created_at:%Y-%m-%d %H:%M} - {self.actor_label}: {self.action}'
