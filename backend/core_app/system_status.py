"""Single source of truth for whether the canteen is accepting orders.

Two things decide that, and this module is where they are combined:

    1. the timetable -- Mon-Fri, 8:00 AM to 5:00 PM (core_app.utils). It runs
       the canteen by itself: the default state is "open during the window,
       closed outside it", with no human involved.
    2. the override   -- what staff last chose on their dashboard, stored in the
       SystemStatus row. FORCE_OPEN extends the day past 5:00 PM; FORCE_CLOSED
       stops orders early with a reason the customer will read.

Why this module exists instead of a plain model lookup:

    The status is read on *every* request -- the gate middleware and the context
    processor both need it. That makes a database round trip per request
    unacceptable, so reads are served from a two-level cache and the row is only
    touched on a cache miss or when staff actually change the mode.

    L1 is a tiny per-process memo (absorbs the several reads a single page load
    generates). L2 is Django's configured cache, which is Redis on Railway (so a
    change is visible to all gunicorn workers) or the shared file cache locally.
    Writing deletes both levels, so a new state propagates in about a second.

    Only the ROW is cached. The timetable is evaluated on every read from the
    cached row, which costs a datetime comparison and keeps the 5:00 PM boundary
    exact even though the row itself is cached for minutes.

Failure policy: a read NEVER raises. If the row or the cache is unreachable the
app falls back to the timetable (and treats a broken timetable as open), because
a canteen that refuses to serve food because a status row could not be read is
worse than one that keeps selling.
"""

import logging
import time

from django.core.cache import cache

# Imported as a module (not `from ... import is_operating_hours`) so that
# patching core_app.utils.is_operating_hours -- which the test suite does -- is
# actually observed here.
from core_app import utils as core_utils
from core_app.closure_reasons import DEFAULT_MESSAGE, label_for, resolve_message

logger = logging.getLogger(__name__)

CACHE_KEY = 'core:system_status:v2'
CACHE_SECONDS = 300  # safety net only; every write deletes the key
LOCAL_TTL = 1.0      # seconds a worker may trust its own memo

# The three states. Defined here rather than on the model because this is where
# the state machine lives; core_app.models imports these for its choices.
MODE_AUTO = 'AUTO'
MODE_FORCE_OPEN = 'FORCE_OPEN'
MODE_FORCE_CLOSED = 'FORCE_CLOSED'
VALID_MODES = (MODE_AUTO, MODE_FORCE_OPEN, MODE_FORCE_CLOSED)
MODE_LABELS = {
    MODE_AUTO: 'Automatic schedule',
    MODE_FORCE_OPEN: 'Open (extended)',
    MODE_FORCE_CLOSED: 'Closed',
}

# Written by the timetable rather than by a person -- see closure_reasons.
SCHEDULE_REASON_CODE = 'OPERATING_HOURS'

DEFAULT_STATUS = {
    'mode': MODE_AUTO,
    'message': '',
    'reason_code': '',
    'reason_label': '',
    'closed_at': None,
    'reopened_at': None,
    'updated_at': None,
}

# {key: (monotonic_deadline, payload)}
_local = {}


def _payload(row):
    """JSON-serializable snapshot of the row (the cache stores dicts)."""
    return {
        'mode': row.mode or MODE_AUTO,
        'message': row.message or '',
        'reason_code': row.reason_code or '',
        'reason_label': label_for(row.reason_code),
        'closed_at': row.closed_at.isoformat() if row.closed_at else None,
        'reopened_at': row.reopened_at.isoformat() if row.reopened_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def resolve_status(raw, now=None):
    """Apply the timetable to a cached row and return the customer-facing state.

    Deliberately free of database and cache access: it is called on every read,
    and it must reflect the exact minute on the clock rather than whenever the
    row happened to be cached. `now` is injectable for tests.
    """
    data = dict(raw or DEFAULT_STATUS)

    mode = str(data.get('mode') or MODE_AUTO).upper()
    if mode not in VALID_MODES:
        mode = MODE_AUTO
    data['mode'] = mode
    data['mode_label'] = MODE_LABELS[mode]
    data['is_override'] = mode != MODE_AUTO

    schedule_open = core_utils.is_operating_hours(now)
    data['schedule_open'] = schedule_open

    if mode == MODE_FORCE_OPEN:
        data['is_open'] = True
    elif mode == MODE_FORCE_CLOSED:
        data['is_open'] = False
        if not data.get('message'):
            data['message'] = DEFAULT_MESSAGE
    elif schedule_open:
        # On the timetable and inside the window: nothing to report.
        data['is_open'] = True
        data['message'] = ''
        data['reason_code'] = ''
        data['reason_label'] = ''
    else:
        # The timetable closed us. Customers get the window and when it reopens.
        data['is_open'] = False
        data['message'] = core_utils.schedule_closed_message(now)[:200]
        data['reason_code'] = SCHEDULE_REASON_CODE
        data['reason_label'] = label_for(SCHEDULE_REASON_CODE)

    # There is no separate "accepting" flag any more: the schedule is already
    # folded into is_open, and a FORCE_OPEN override has to win over the clock.
    data['accepting_orders'] = bool(data['is_open'])
    return data


def _raw_status(force=False):
    """The cached row: memo -> shared cache -> database, in that order."""
    now = time.monotonic()

    if not force:
        memo = _local.get(CACHE_KEY)
        if memo and memo[0] > now:
            return dict(memo[1])

    data = None
    try:
        data = cache.get(CACHE_KEY)
    except Exception:
        # A cache backend outage must not 500 the whole site.
        logger.exception('System status cache read failed')

    if data is None:
        data = _read_db()
        try:
            cache.set(CACHE_KEY, data, CACHE_SECONDS)
        except Exception:
            logger.exception('System status cache write failed')

    _local[CACHE_KEY] = (time.monotonic() + LOCAL_TTL, data)
    return dict(data)


def _read_db():
    from .models import SystemStatus

    try:
        row = SystemStatus.objects.filter(pk=1).first()
        if row is None:
            # First ever read: materialise the singleton on the schedule.
            row = SystemStatus.objects.create(pk=1)
        return _payload(row)
    except Exception:
        # Missing table (before the migration runs) or a database outage.
        logger.exception('Could not read SystemStatus; falling back to the schedule')
        return dict(DEFAULT_STATUS)


def get_status(force=False):
    """Return the resolved switch as a plain dict. Cached, memoised, never raises.

    Callers get a copy: the memo is process-wide, so handing out the cached
    object itself would let one careless `status['is_open'] = True` corrupt
    every later request in that worker.
    """
    return resolve_status(_raw_status(force))


def is_open():
    """True when the canteen is open right now, timetable included."""
    return bool(get_status()['is_open'])


def is_accepting_orders():
    """The checkout gate. Identical to is_open(); kept as the named call site."""
    return bool(get_status()['is_open'])


def invalidate():
    """Drop both cache levels so the next read comes from the database."""
    _local.pop(CACHE_KEY, None)
    try:
        cache.delete(CACHE_KEY)
    except Exception:
        logger.exception('System status cache invalidation failed')


def set_mode(mode, reason_code='', message='', user=None):
    """Set the override and return the resolved state.

    `AUTO` hands control back to the timetable (this is how staff undo an
    extension). `FORCE_CLOSED` needs a reason: `reason_code` is a preset from
    core_app.closure_reasons and the customer-facing text is derived from it, so
    callers cannot accidentally publish an internal-sounding note. `message` is
    only used for the `OTHER` preset (or when no code is given).
    """
    from django.utils import timezone

    from .models import SystemStatus

    mode = str(mode or '').strip().upper()
    if mode not in VALID_MODES:
        mode = MODE_AUTO

    row, _created = SystemStatus.objects.get_or_create(pk=1)
    now = timezone.now()

    row.mode = mode
    if mode == MODE_FORCE_CLOSED:
        row.reason_code = str(reason_code or '').strip().upper()[:32]
        row.message = resolve_message(row.reason_code, message)[:200]
        row.closed_at = now
    else:
        row.reason_code = ''
        row.message = ''
        if mode == MODE_FORCE_OPEN:
            row.reopened_at = now

    if user is not None and getattr(user, 'is_authenticated', False):
        row.updated_by = user
    row.save()

    invalidate()
    return resolve_status(_payload(row))


def set_open(open_now, reason_code='', message='', user=None):
    """Back-compatible wrapper: True extends, False closes with a reason."""
    return set_mode(
        MODE_FORCE_OPEN if open_now else MODE_FORCE_CLOSED,
        reason_code=reason_code,
        message=message,
        user=user,
    )
