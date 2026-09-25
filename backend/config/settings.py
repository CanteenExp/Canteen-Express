import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env at mag-print ng diagnostic info (override=True so .env takes precedence)
env_file = BASE_DIR / ".env"
dotenv_loaded = load_dotenv(env_file, override=True)

print("\n" + "="*40)
print(f"Checking .env path: {env_file}")
print(f"File exists: {env_file.exists()}")
print(f"DB_PASSWORD Loaded: {'YES' if os.getenv('DB_PASSWORD') else 'NO (Empty/None)'}")
geofence_status = os.getenv('ENFORCE_GEOFENCE', 'True').lower() == 'true'
print(f"Geofence Enforcement: {'ENABLED (Strict Campus Radius)' if geofence_status else 'DISABLED (Testing Anywhere Mode)'}")
print("="*40 + "\n")

# Quick-start development settings - unsuitable for production
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-local-dev-key")

DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t", "yes")

# Google Maps JS API key (from backend/.env). When empty/absent, the map engine
# facade falls back to free OpenStreetMap tiles so the app keeps working offline.
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '.onrender.com', '.loca.lt', '.devtunnels.ms', '.railway.app']
AUTH_USER_MODEL = 'accounts.CustomUser'

# Staff "Admin / System" governance PIN. MUST be overridden via env in production
# (the default '1234' is a dev fallback only and is intentionally removed from
# the shipped render.yaml config).
ADMIN_PIN = os.getenv('ADMIN_PIN', '1234')

# Supabase Storage credentials for menu image uploads. The anon key is public
# by nature (client-side bucket access) but is centralized here so it can be
# rotated/overridden per environment without code changes.
SUPABASE_PROJECT_REF = os.getenv('SUPABASE_PROJECT_REF', 'hchqdkuijbpihraagetz')
SUPABASE_ANON_KEY = os.getenv(
    'SUPABASE_ANON_KEY',
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhjaHFka3VpamJwaWhyYWFnZXR6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg4MzU1MDMsImV4cCI6MjEwNDQxMTUwM30.FevR0wpG7Kk7YgNO30Hi8Jvz-Z8rXiWNPBVoM4LbqUA',
)

# Application definition

INSTALLED_APPS = [
    # Django Core Apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Local Canteen Express Apps
    'accounts',
    'customer_portal',
    'canteen_menu',
    'order_management',
    'queuing',
    'deliveries',
    'user_notifications',
    'analytics_reports',
    'admin_dashboard',
    'kitchen_display',
    'core_app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

# Role-aware post-login fallback (the dedicated role login views redirect explicitly,
# this only guards the generic /accounts/login/ page from dumping users on a dead URL).
LOGIN_REDIRECT_URL = 'accounts:landing'
LOGIN_URL = 'accounts:landing'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core_app.context_processors.map_key',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database (Strict Supabase PostgreSQL + SQLite backup source with automatic fallback)
USE_SQLITE = os.getenv('USE_SQLITE', 'False').lower() == 'true'
db_host = os.getenv('DB_HOST', '')

if USE_SQLITE or not db_host:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'postgres'),
            'USER': os.getenv('DB_USER', ''),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', ''),
            'PORT': os.getenv('DB_PORT', '6543'),
            'CONN_MAX_AGE': 600,
            'OPTIONS': {
                'sslmode': 'require',
                'connect_timeout': 5,
            },
        },
        'sqlite_backup': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Session Persistence Settings (Prevent Auto-Logout)
SESSION_COOKIE_AGE = 1209600  # 2 weeks
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Manila'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# Cross-worker cache so menu edits invalidate everywhere (Redis when configured,
# shared file-based cache otherwise so cache.delete() actually propagates).
REDIS_URL = os.getenv('REDIS_URL', '')
if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
            'LOCATION': os.path.join(BASE_DIR, 'django_cache'),
        }
    }

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Email Settings (Real-time SMTP Gmail SSL Port 465)
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 465))
_use_ssl = (os.getenv('EMAIL_USE_SSL') or '').lower() == 'true'
_use_tls = (os.getenv('EMAIL_USE_TLS') or '').lower() == 'true'
# Transport is derived from the port so Gmail always works: 587 needs STARTTLS,
# 465 needs implicit SSL. Explicit env values win, but a contradictory pair
# (both SSL and TLS true) is resolved by the port instead of breaking sends.
if _use_ssl and _use_tls:
    EMAIL_USE_SSL = EMAIL_PORT == 465
    EMAIL_USE_TLS = EMAIL_PORT == 587
elif _use_ssl or _use_tls:
    EMAIL_USE_SSL = _use_ssl
    EMAIL_USE_TLS = _use_tls
else:
    EMAIL_USE_SSL = EMAIL_PORT == 465
    EMAIL_USE_TLS = EMAIL_PORT == 587
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', 'canteenexpress26@gmail.com')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
# Fail fast when SMTP is unreachable/blocked (e.g. Railway egress) instead of
# blocking the worker until gunicorn kills it; the OTP fallback then takes over.
EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT', 10))
# From address always follows the authenticated SMTP account so Gmail never
# rejects a mismatched sender (works on Railway/Render the same as locally).
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', f'Canteen Express <{EMAIL_HOST_USER}>')


CSRF_TRUSTED_ORIGINS = [
    'https://tiny-boats-win.loca.lt',
    'https://*.loca.lt',
    'https://*.devtunnels.ms',
    'https://*.onrender.com',
    'https://*.railway.app',
    'https://*.localhost',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

# Behind Railway/Render/Cloudflare the app is always served over HTTPS, but
# Django only sees the raw proxy connection. Tell it to trust the proxy's
# X-Forwarded-Proto so request.is_secure()/CSRF/absolute URLs match the
# browser's https origin (otherwise fetch POSTs 403/redirect in production).
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Production-only transport security: secure session/CSRF cookies, HSTS, and
# sniffing/referrer protection. Kept off in DEBUG so local forwarded-port
# (http://localhost:8000) dev keeps working without forced HTTPS redirects.
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'same-origin'

ENFORCE_GEOFENCE = os.getenv('ENFORCE_GEOFENCE', 'True').lower() == 'true'
