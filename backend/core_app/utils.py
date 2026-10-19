"""The canteen's automatic timetable.

The canteen runs itself on a schedule -- Monday to Friday, 8:00 AM to 5:00 PM,
Asia/Manila. That is the DEFAULT: outside those windows ordering closes on its
own, with nobody pressing anything.

A human can always override the timetable from the staff dashboard (see
core_app.system_status): force it open to *extend* the day, or close it early
with a reason. This module only answers one question -- "does the timetable say
we should be open right now?" -- and the status service folds that answer into
the switch it hands to the rest of the app.

The window lives in settings (with env-var overrides) so it can be tuned per
deployment without a code change, and every function accepts an explicit `now`
so the behaviour is testable without freezing the clock.
"""

from datetime import datetime, time, timedelta

from django.conf import settings
from django.utils import timezone

# Fallbacks used when settings (or a deployment) do not define a window.
DEFAULT_DAYS = (0, 1, 2, 3, 4)  # Monday..Friday
DEFAULT_OPEN_HOUR = 8
DEFAULT_CLOSE_HOUR = 17

_DAY_NAMES = (
    'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
)


def operating_days():
    """Weekdays the canteen is open, as Python weekday numbers (Mon = 0)."""
    days = getattr(settings, 'OPERATING_HOURS_DAYS', DEFAULT_DAYS)
    try:
        return tuple(int(day) for day in days)
    except (TypeError, ValueError):
        return DEFAULT_DAYS


def open_hour():
    return int(getattr(settings, 'OPERATING_HOURS_START', DEFAULT_OPEN_HOUR))


def close_hour():
    return int(getattr(settings, 'OPERATING_HOURS_END', DEFAULT_CLOSE_HOUR))


def is_operating_hours(now=None):
    """True when the timetable says the canteen should be open.

    With no `now` the real clock is used, and the check can be switched off
    entirely with ENFORCE_OPERATING_HOURS (tests, and anyone who wants the app
    to behave like the pre-schedule build). Passing an explicit `now` always
    evaluates the window, because a caller who brings their own clock wants the
    timetable answer, not the kill switch.
    """
    if now is None:
        if not getattr(settings, 'ENFORCE_OPERATING_HOURS', True):
            return True
        try:
            now = timezone.localtime()
        except Exception:
            # A broken TIME_ZONE must never take ordering down with it.
            return True

    if now.weekday() not in operating_days():
        return False
    return open_hour() <= now.hour < close_hour()


def format_hour(hour):
    """8 -> '8:00 AM', 17 -> '5:00 PM'."""
    hour = int(hour) % 24
    suffix = 'AM' if hour < 12 else 'PM'
    return f'{hour % 12 or 12}:00 {suffix}'


def operating_days_text():
    """'Monday to Friday' when contiguous, else 'Monday, Wednesday, Friday'."""
    days = sorted(operating_days())
    if not days:
        return 'no scheduled days'
    if days == list(DEFAULT_DAYS):
        return 'Monday to Friday'
    return ', '.join(_DAY_NAMES[day] for day in days)


def operating_hours_text():
    """The full window, ready to drop into a customer-facing sentence."""
    return (f'{operating_days_text()}, '
            f'{format_hour(open_hour())} to {format_hour(close_hour())}')


def next_opening(now=None):
    """The next moment the timetable opens, or None if it never does."""
    now = now or timezone.localtime()
    days = operating_days()
    if not days:
        return None

    for offset in range(0, 8):
        day = (now + timedelta(days=offset)).date()
        if day.weekday() not in days:
            continue
        naive = datetime.combine(day, time(open_hour(), 0))
        if now.tzinfo is not None:
            candidate = timezone.make_aware(naive, now.tzinfo)
        else:
            candidate = naive
        if candidate > now:
            return candidate
    return None


def next_opening_text(now=None):
    """'today at 8:00 AM' / 'tomorrow at 8:00 AM' / 'on Monday at 8:00 AM'."""
    now = now or timezone.localtime()
    target = next_opening(now)
    if target is None:
        return ''

    days_away = (target.date() - now.date()).days
    if days_away <= 0:
        return f'today at {format_hour(open_hour())}'
    if days_away == 1:
        return f'tomorrow at {format_hour(open_hour())}'
    return f'on {target.strftime("%A")} at {format_hour(open_hour())}'


def schedule_closed_message(now=None):
    """What a customer reads when the timetable (not a human) closed us."""
    message = f'We accept orders {operating_hours_text()}.'
    when = next_opening_text(now)
    if when:
        message = f'{message} Ordering opens again {when}.'
    return message
