from django.conf import settings


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