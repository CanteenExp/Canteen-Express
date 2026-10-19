from django.conf import settings
from django.utils import timezone
from django.utils.functional import SimpleLazyObject

from core_app import utils as core_utils
from core_app.closure_reasons import CLOSURE_REASONS
from core_app.system_status import get_status, is_accepting_orders
from core_app.utils import is_operating_hours


def map_key(request):
    """Inject the Google Maps API key (+ a flag) into every template context.

    - GOOGLE_MAPS_API_KEY: raw key from backend/.env ('' when unset)
    - USE_GOOGLE_MAPS: True when a key is configured, so templates can load the
      Maps JS script only when needed.
    """
    key = getattr(settings, 'GOOGLE_MAPS_API_KEY', '') or ''
    return {
        'GOOGLE_MAPS_API_KEY': key,
        'USE_GOOGLE_MAPS': bool(key),
    }


def operating_hours_status(request):
    """Inject whether the store is within operating hours (Mon-Fri 8am-5pm) into context."""
    now = timezone.localtime()
    return {
        'IS_OPERATING_HOURS': is_operating_hours(),
        'CURRENT_DAY_NAME': now.strftime('%A'),
        'CURRENT_TIME_FORMATTED': now.strftime('%B %d, %Y - %I:%M %p'),
    }


def system_status(request):
    """Inject the canteen's open/close state into every template context.

    Templates use SYSTEM_IS_OPEN to render the "closed" banner and to disable
    ordering buttons, and the staff dashboards use SYSTEM_MODE to draw the
    schedule / extend / close controls. The values are deliberately LAZY: a page
    that never renders the banner (the vast majority) never pays for a cache
    read, let alone a query -- which matters because this runs on every render.
    """
    lazy_status = SimpleLazyObject(get_status)
    return {
        'SYSTEM_IS_OPEN': SimpleLazyObject(lambda: lazy_status['is_open']),
        'SYSTEM_CLOSED_MESSAGE': SimpleLazyObject(lambda: lazy_status['message']),
        'SYSTEM_CLOSED_AT': SimpleLazyObject(lambda: lazy_status['closed_at']),
        'ACCEPTING_ORDERS': SimpleLazyObject(is_accepting_orders),
        # Override state, for the staff dashboards' three-way control.
        'SYSTEM_MODE': SimpleLazyObject(lambda: lazy_status['mode']),
        'SYSTEM_MODE_LABEL': SimpleLazyObject(lambda: lazy_status['mode_label']),
        'SYSTEM_IS_OVERRIDE': SimpleLazyObject(lambda: lazy_status['is_override']),
        'SYSTEM_SCHEDULE_OPEN': SimpleLazyObject(lambda: lazy_status['schedule_open']),
        'SYSTEM_REASON_LABEL': SimpleLazyObject(lambda: lazy_status['reason_label']),
        'SYSTEM_OPERATING_HOURS': SimpleLazyObject(core_utils.operating_hours_text),
        'SYSTEM_NEXT_OPENING': SimpleLazyObject(core_utils.next_opening_text),
        # A module-level constant, so handing it out costs nothing and the
        # staff dashboards can render their dropdown without a view change.
        'CLOSURE_REASONS': CLOSURE_REASONS,
    }
