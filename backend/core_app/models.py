from django.conf import settings
from django.db import models

from .closure_reasons import label_for
# The state machine lives in the service; the model only stores it.
from .system_status import (
    MODE_AUTO as _MODE_AUTO,
    MODE_FORCE_CLOSED as _MODE_FORCE_CLOSED,
    MODE_FORCE_OPEN as _MODE_FORCE_OPEN,
)


class SystemStatus(models.Model):
    """Singleton row (always pk=1) holding the canteen's open/close state.

    There are three states, because the canteen now runs itself on a timetable
    (core_app.utils) and the manual control is an *override* of that timetable:

        AUTO          -- follow the schedule (Mon-Fri, 8:00 AM - 5:00 PM).
                         The default, and what a fresh install does.
        FORCE_OPEN    -- stay open regardless of the clock. This is how staff
                         "extend" the day past 5:00 PM.
        FORCE_CLOSED  -- stay closed regardless of the clock, with a reason
                         preset the customer will read.

    This value is consulted on *every* request (middleware + context processor),
    so it is never read with a query in the hot path. core_app.system_status
    serves it from the shared cache; this table is only the durable source of
    truth that cache is rebuilt from.
    """

    MODE_AUTO = _MODE_AUTO
    MODE_FORCE_OPEN = _MODE_FORCE_OPEN
    MODE_FORCE_CLOSED = _MODE_FORCE_CLOSED
    MODE_CHOICES = (
        (MODE_AUTO, 'Automatic schedule (Mon-Fri, 8:00 AM - 5:00 PM)'),
        (MODE_FORCE_OPEN, 'Force open (overrides the schedule)'),
        (MODE_FORCE_CLOSED, 'Force closed (overrides the schedule)'),
    )

    mode = models.CharField(
        max_length=16,
        choices=MODE_CHOICES,
        default=MODE_AUTO,
        help_text=(
            'AUTO follows operating hours; FORCE_OPEN / FORCE_CLOSED override '
            'the schedule until staff set it back to AUTO.'
        ),
    )
    message = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text='Customer-facing text. Filled in from the chosen reason preset.',
    )
    reason_code = models.CharField(
        max_length=32,
        blank=True,
        default='',
        help_text='Preset key from core_app.closure_reasons (e.g. SYSTEM_UPDATE).',
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

    @property
    def is_open(self):
        """The manual switch alone: is it currently forcing the canteen closed?

        The schedule is applied on top of this in core_app.system_status; keep
        the two separate or the timetable would be impossible to reason about.
        """
        return self.mode != self.MODE_FORCE_CLOSED

    def __str__(self):
        if self.mode == self.MODE_FORCE_OPEN:
            return 'Canteen is OPEN (forced open)'
        if self.mode != self.MODE_FORCE_CLOSED:
            return 'Canteen is OPEN (automatic schedule)'
        label = label_for(self.reason_code)
        if label:
            return f'Canteen is CLOSED ({label})'
        return f'Canteen is CLOSED ({self.message})' if self.message else 'Canteen is CLOSED'
