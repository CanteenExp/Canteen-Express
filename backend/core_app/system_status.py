"""Single source of truth for the manual "canteen is open" switch.

Why this module exists instead of a plain model lookup:

    The switch is read on *every* request -- the gate middleware and the
    context processor both need it. That makes a database round trip per
    request unacceptable, so reads are served from a two-level cache and the
    row is only touched on a cache miss or when staff actually flip it.

    L1 is a tiny per-process memo (absorbs the several reads a single page load
    generates). L2 is Django's configured cache, which is Redis on Railway (so
    the flip is visible to all gunicorn workers) or the shared file cache
    locally. Writing deletes both levels, so being "closed" propagates in about
    a second, which is far faster than a human can react to anyway.

Failure policy: a read NEVER raises. If the row or the cache is unreachable the
app assumes OPEN, because a canteen that refuses to serve food because a status
row could not be read is worse than one that keeps selling.
"""

import logging
import time

from django.core.cache import cache

# Imported as a module (not `from ... import is_operating_hours`) so that
# patching core_app.utils.is_operating_hours -- which the test suite and any
# future caller may do -- is actually observed here.
from core_app import utils as core_utils

logger = logging.getLogger(__name__)

CACHE_KEY = 'core:system_status:v1'
CACHE_SECONDS = 300  # safety net only; every write deletes the key
LOCAL_TTL = 1.0      # seconds a worker may trust its own memo

DEFAULT_STATUS = {
    'is_open': True,
    'message': '',
    'closed_at': None,
    'reopened_at': None,
    'updated_at': None,
}

# {key: (monotonic_deadline, payload)}
_local = {}


def _payload(row):
    """JSON-serializable snapshot of the row (the cache stores dicts)."""
    return {
        'is_open': bool(row.is_open),
        'message': row.message or '',
        'closed_at': row.closed_at.isoformat() if row.closed_at else None,
        'reopened_at': row.reopened_at.isoformat() if row.reopened_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def _read_db():
    from .models import SystemStatus

    try:
        row = SystemStatus.objects.filter(pk=1).first()
        if row is None:
            # First ever read: materialise the singleton as OPEN.
            row = SystemStatus.objects.create(pk=1)
        return _payload(row)
    except Exception:
        # Missing table (before the migration runs) or a database outage.
        logger.exception('Could not read SystemStatus; assuming the canteen is OPEN')
        return dict(DEFAULT_STATUS)


def get_status(force=False):
    """Return the switch as a plain dict. Cached, memoised, never raises.

    Callers get a copy: the memo is process-wide, so handing out the cached
    object itself would let one careless `status['is_open'] = True` corrupt
    every later request in that worker.
    """
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


def is_open():
    """True when staff have left the canteen open for orders."""
    return bool(get_status()['is_open'])


def is_accepting_orders():
    """The real checkout gate: staff switch AND configured operating hours."""
    return is_open() and core_utils.is_operating_hours()


def invalidate():
    """Drop both cache levels so the next read comes from the database."""
    _local.pop(CACHE_KEY, None)
    try:
        cache.delete(CACHE_KEY)
    except Exception:
        logger.exception('System status cache invalidation failed')


def set_open(open_now, message='', user=None):
    """Flip the switch and return the new payload."""
    from django.utils import timezone

    from .models import SystemStatus

    row, _created = SystemStatus.objects.get_or_create(pk=1)
    row.is_open = bool(open_now)
    if row.is_open:
        row.message = ''
        row.reopened_at = timezone.now()
    else:
        row.message = (message or '').strip()[:200]
        row.closed_at = timezone.now()

    if user is not None and getattr(user, 'is_authenticated', False):
        row.updated_by = user
    row.save()

    invalidate()
    return _payload(row)
