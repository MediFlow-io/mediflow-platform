import os
from datetime import timedelta
from pathlib import Path

from .jwt_keys import load_keys

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-development-key-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host.strip()]

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "django_prometheus", "corsheaders", "rest_framework", "rest_framework_simplejwt.token_blacklist", "apps.accounts", "apps.patients", "apps.operations", "apps.ai", "apps.notifications", "apps.clinic",
]
# Prometheus middleware wraps everything else (first and last) to time whole requests.
MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware", "corsheaders.middleware.CorsMiddleware", "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True,
              "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION = "config.wsgi.application"

if os.getenv("POSTGRES_DB"):
    DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": os.environ["POSTGRES_DB"], "USER": os.environ["POSTGRES_USER"], "PASSWORD": os.environ["POSTGRES_PASSWORD"], "HOST": os.getenv("POSTGRES_HOST", "db"), "PORT": os.getenv("POSTGRES_PORT", "5432")}}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

AUTH_USER_MODEL = "accounts.User"
# Enforced in every environment (registration and password changes).
AUTH_PASSWORD_VALIDATORS = [{"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
                            {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
                            {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"}]
LANGUAGE_CODE, TIME_ZONE, USE_I18N, USE_TZ = "en-us", "Africa/Lagos", True, True
STATIC_URL, STATIC_ROOT = "/static/", BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
# JWT (RS256) for the React client and other services; sessions for the legacy FUTA frontend.
REST_FRAMEWORK = {"DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication", "rest_framework.authentication.SessionAuthentication"], "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"], "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"], "DEFAULT_THROTTLE_RATES": {"ai": os.getenv("AI_RATE_LIMIT", "30/min"), "login": os.getenv("LOGIN_RATE_LIMIT", "10/min"), "register": os.getenv("REGISTER_RATE_LIMIT", "20/hour")}}
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500,http://localhost:3000").split(",") if origin.strip()]
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG

JWT_PRIVATE_KEY, JWT_PUBLIC_KEY = load_keys(Path(os.getenv("JWT_KEYS_DIR", BASE_DIR / ".keys")), DEBUG)
# TODO(decision): the MVP brief asks for a Redis revocation list. Redis is not part of this
# deployment yet, so revoked refresh tokens use SimpleJWT's database blacklist instead.
SIMPLE_JWT = {
    "ALGORITHM": "RS256",
    "SIGNING_KEY": JWT_PRIVATE_KEY,
    "VERIFYING_KEY": JWT_PUBLIC_KEY,
    "ISSUER": os.getenv("JWT_ISSUER", "mediflow-core"),
    "AUDIENCE": os.getenv("JWT_AUDIENCE", "mediflow"),
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "10"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

# Internal FastAPI AI service. Reached only from Django, never from browsers.
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8001")
AI_SERVICE_TOKEN = os.getenv("AI_SERVICE_TOKEN", "mediflow-dev-internal-token")
AI_SERVICE_TIMEOUT = float(os.getenv("AI_SERVICE_TIMEOUT", "3"))
if not DEBUG and AI_SERVICE_TOKEN == "mediflow-dev-internal-token":
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("Set AI_SERVICE_TOKEN to a unique secret shared with the AI service.")
