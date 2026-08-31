import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env at mag-print ng diagnostic info
env_file = BASE_DIR / ".env"
dotenv_loaded = load_dotenv(env_file)

print("\n" + "="*40)
print(f"Checking .env path: {env_file}")
print(f"File exists: {env_file.exists()}")
print(f"DB_PASSWORD Loaded: {'YES' if os.getenv('DB_PASSWORD') else 'NO (Empty/None)'}")
print("="*40 + "\n")

# Quick-start development settings - unsuitable for production
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-local-dev-key")

DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '*']
AUTH_USER_MODEL = 'accounts.CustomUser'

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
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
use_sqlite = os.getenv('USE_SQLITE', 'False').lower() == 'true'

if use_sqlite:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    db_host = os.getenv('DB_HOST', 'ep-shy-heart-ayghwl06-pooler.c-5.us-east-2.aws.neon.tech')
    db_name = os.getenv('DB_NAME', 'neondb')
    db_user = os.getenv('DB_USER', 'neondb_owner')
    db_password = os.getenv('DB_PASSWORD')
    db_port = os.getenv('DB_PORT', '5432')

    # Wake up Neon serverless compute instance if suspended / cold start
    import time
    try:
        import psycopg2
        for attempt in range(3):
            try:
                conn = psycopg2.connect(
                    dbname=db_name,
                    user=db_user,
                    password=db_password,
                    host=db_host,
                    port=db_port,
                    connect_timeout=5,
                    sslmode='require'
                )
                conn.close()
                break
            except Exception:
                if attempt < 2:
                    time.sleep(2.5)
    except Exception:
        pass

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': db_name,
            'USER': db_user,
            'PASSWORD': db_password,
            'HOST': db_host,
            'PORT': db_port,
            'OPTIONS': {
                'sslmode': 'require',
                'connect_timeout': 20,
            },
        }
    }


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
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Print emails to the console for testing during development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'Canteen Express <no-reply@canteenexpress.com>'


CSRF_TRUSTED_ORIGINS = [
    'https://tiny-boats-win.loca.lt',
    'https://*.loca.lt', 
]
