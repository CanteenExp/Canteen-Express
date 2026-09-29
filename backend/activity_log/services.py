"""Central helper for recording staff activity.

Design rule that matters most: log_activity() NEVER raises. It is called from
inside payment confirmation, menu updates and user-status changes -- if writing a
log row could throw, a failed INSERT would roll back or mask the real business
action the user asked for. A missing log row is recoverable; a failed payment is
not. So every failure here is swallowed and reported through the logger.
"""
import logging

from .models import ActivityLog

logger = logging.getLogger(__name__)

# Header names that sit in front of a reverse proxy. Without these the recorded
# IP is the proxy's, not the staff member's, which makes the log far less useful.
FORWARDED_HEADERS = ('HTTP_X_FORWARDED_FOR', 'HTTP_X_REAL_IP')


def resolve_actor(request):
    """Return (user_or_None, display_label) for an incoming request.

    Falls back to a label derived from the session so kiosk / POS actions made by
    a signed-in staff member on a shared terminal are still attributed.
    """
    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        return user, _display_name(user)
    return None, 'System'


def _display_name(user):
    """Project convention: get_full_name with a username fallback.

    Matches the ~20 existing call sites (base.html:86, staff_dashboard.html:471).
    """
    try:
        name = user.get_full_name().strip()
    except Exception:
        name = ''
    if not name:
        name = getattr(user, 'username', '') or ''
    return name[:150] or 'System'


def client_ip(request):
    """Best-effort client IP, honouring the first entry of X-Forwarded-For."""
    try:
        for header in FORWARDED_HEADERS:
            raw = request.META.get(header)
            if raw:
                return raw.split(',')[0].strip()[:45]
        return request.META.get('REMOTE_ADDR', '')[:45] or None
    except Exception:
        return None


def log_activity(request=None, action='', category=ActivityLog.Category.SYSTEM,
                 level=ActivityLog.Level.INFO, actor=None, actor_label='',
                 target='', metadata=None, is_guest=False):
    """Record one activity row. Returns the ActivityLog, or None on failure.

    Keyword-only after `action` is deliberate: category/level are the fields a
    caller always sets, and the rest have sensible defaults.
    """
    try:
        if actor is None and request is not None:
            actor, derived_label = resolve_actor(request)
            if not actor_label:
                actor_label = derived_label

        if metadata is not None and not isinstance(metadata, dict):
            metadata = {'value': str(metadata)}

        return ActivityLog.objects.create(
            actor=actor,
            actor_label=(actor_label or _display_name(actor))[:150] if actor else 'System',
            category=category,
            level=level,
            action=str(action)[:255],
            target=str(target or '')[:200],
            metadata=metadata or {},
            is_guest=bool(is_guest),
        )
    except Exception:
        # Swallow deliberately -- see the module docstring.
        logger.exception('Failed to record activity log entry: %s', action[:120])
        return None


def log_menu_change(request, item, verb, level=ActivityLog.Level.INFO, **metadata):
    """Convenience wrapper for the menu/stock actions, which are by far the
    most frequent and all share the same phrasing."""
    return log_activity(
        request,
        action=verb,
        category=ActivityLog.Category.MENU,
        level=level,
        target=item.name,
        metadata=metadata,
    )
