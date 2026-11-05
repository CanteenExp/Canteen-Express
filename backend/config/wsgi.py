"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os
from pathlib import Path

from django.conf import settings
from django.core.wsgi import get_wsgi_application
from whitenoise import WhiteNoise

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()

# Django's `static()` helper only serves MEDIA_URL while DEBUG=True, so a photo
# stored on local disk (the fallback used when Supabase Storage is unavailable)
# would 404 in production. WhiteNoise serves it straight from MEDIA_ROOT.
# Only menu_items is exposed on purpose: delivery proof photos stay private.
_media_root = Path(settings.MEDIA_ROOT) / 'menu_items'
if _media_root.is_dir():
    application = WhiteNoise(application)
    application.add_files(str(_media_root), prefix='media/menu_items/')
