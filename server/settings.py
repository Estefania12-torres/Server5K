"""
Django settings para producción segura.
"""

import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

# === SEGURIDAD CRÍTICA ===
# La SECRET_KEY DEBE venir de variables de entorno en producción
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-dev-key-change-in-production')

# DEBUG debe ser False explícitamente en producción
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')

# ALLOWED_HOSTS - Configurable vía variable de entorno
_allowed_hosts_env = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_env.split(',') if h.strip()]

_csrf_origins_env = os.getenv('CSRF_TRUSTED_ORIGINS', '')
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins_env.split(',') if o.strip()]

_cors_origins_env = os.getenv('CORS_ALLOWED_ORIGINS', '')
CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_origins_env.split(',') if o.strip()]



INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'channels',
    'drf_spectacular',
    'app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'server.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'server.wsgi.application'
ASGI_APPLICATION = 'server.asgi.application'

# === REDIS (Channels) ===
REDIS_HOST = os.getenv('REDIS_HOST', '127.0.0.1')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [(REDIS_HOST, REDIS_PORT)],
            'capacity': 10000,
            'expiry': 60,
            'prefix': 'server5k',
        },
    },
}

# === BASE DE DATOS (PostgreSQL) ===
# Usa SQLite como fallback para desarrollo si no hay configuración de PostgreSQL
_postgres_db = os.getenv('POSTGRES_DB')

if _postgres_db:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': _postgres_db,
            'USER': os.getenv('POSTGRES_USER', 'server5k'),
            'PASSWORD': os.getenv('POSTGRES_PASSWORD', ''),
            'HOST': os.getenv('POSTGRES_HOST', 'localhost'),
            'PORT': os.getenv('POSTGRES_PORT', '5432'),
            'CONN_MAX_AGE': 60,
            'OPTIONS': {
                'sslmode': os.getenv('POSTGRES_SSLMODE', 'prefer'),
            },
        }
    }
else:
    # Fallback a SQLite para desarrollo local o durante el build de Docker
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# === VALIDACIÓN DE CONTRASEÑAS ===
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 12}  # Mínimo 12 caracteres para producción
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# === INTERNACIONALIZACIÓN ===
LANGUAGE_CODE = 'es-es'
TIME_ZONE = 'America/Guayaquil'
USE_I18N = True
USE_TZ = True

# === ARCHIVOS ESTÁTICOS ===
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# === ARCHIVOS MEDIA (subidos por usuarios) ===
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'mediafiles'

# === PRIMARY KEY ===
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# === DJANGO REST FRAMEWORK ===
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'app.auth.authentication.JuezJWTAuthentication',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# === DRF-SPECTACULAR (Documentación API) ===
SPECTACULAR_SETTINGS = {
    'TITLE': 'Server5K API',
    'DESCRIPTION': 'API para gestión de competencias 5K con registro de tiempos en tiempo real',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SECURITY': [{'bearerAuth': []}],
    'APPEND_COMPONENTS': {
        'securitySchemes': {
            'bearerAuth': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
            }
        }
    },
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': True,
    },
    'PREPROCESSING_HOOKS': [],
    'SERVE_PERMISSIONS': ['rest_framework.permissions.AllowAny'],
}

# === SIMPLEJWT ===
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'JTI_CLAIM': 'jti',
}

# === CORS (Seguro por defecto) ===
_cors_origins_env = os.getenv('CORS_ALLOWED_ORIGINS', '')
if _cors_origins_env:
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_origins_env.split(',') if o.strip()]
else:
    # En desarrollo local, permite CORS específico
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = ['http://localhost:3000', 'http://127.0.0.1:3000']

CORS_ALLOW_CREDENTIALS = True

# === SEGURIDAD HTTPS ===
# Solo habilitar si estamos en producción real (no Docker local)
_enable_https = os.getenv('ENABLE_HTTPS', 'False').lower() in ('true', '1', 'yes')

if _enable_https:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # 1 año
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

# === EMAIL BACKEND (Configuración básica) ===
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@server5k.com')

# === LOGGING (Configurado para producción) ===
# Crear directorio de logs si no existe
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {name} - {message}',
            'style': '{',
        },
        'simple': {
            'format': '[{levelname}] {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': LOGS_DIR / 'django.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'app.websocket.consumers': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'app.websocket.validators': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'app.services': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.channels': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'WARNING',
    },
}
