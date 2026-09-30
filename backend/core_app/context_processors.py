from django.conf import settings
from django.utils import timezone
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