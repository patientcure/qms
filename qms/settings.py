import os
import json
from pathlib import Path
from datetime import timedelta

import dj_database_url
from dotenv import load_dotenv
from google.oauth2 import service_account
import firebase_admin
from firebase_admin import credentials


load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
# The `str(value).lower() == 'true'` pattern is a safe way to handle boolean env vars.
DEBUG = str(os.getenv('DEBUG', 'False')).lower() == 'true'

# Update this for your production domains
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost,https://qms-3lra.vercel.app,"http://69.62.80.202').split(',')

# --- Application Definitions ---
# --------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',

    # Third-Party Apps
    'rest_framework',
    'corsheaders',
    'widget_tweaks',
    
    # Your Apps
    'apps.accounts',
    'apps.quotations',
]


# --- Middleware ---
# --------------------------------------------------------------------------
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # WhiteNoise middleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'crum.CurrentRequestUserMiddleware'
]


# --- URL & Template Configuration ---
# --------------------------------------------------------------------------
ROOT_URLCONF = 'qms.urls'
WSGI_APPLICATION = 'qms.wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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


# --- Database ---
# --------------------------------------------------------------------------
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }
#Production Database Configuration
DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL'),
    )
}

# --- User & Authentication ---
# --------------------------------------------------------------------------
AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# --- Internationalization & Time ---
# --------------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True


# --- Static & Media Files (with Firebase Storage) ---
# --------------------------------------------------------------------------
# Static files (CSS, JavaScript, Images for your site's template)
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR,'staticfiles') 
GENERATED_FILES_DIR = os.path.join(BASE_DIR,'staticfiles', 'quotations')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files (User-uploaded content)
# 1. Load Firebase credentials from the environment variable
firebase_credentials_json = os.getenv('FIREBASE_CREDENTIALS_JSON')
firebase_credentials_dict = None
if firebase_credentials_json:
    try:
        firebase_credentials_dict = json.loads(firebase_credentials_json)
    except json.JSONDecodeError:
        print("ERROR: Could not decode FIREBASE_CREDENTIALS_JSON.")
else:
    print("WARNING: FIREBASE_CREDENTIALS_JSON environment variable not found.")

# 2. Initialize Firebase Admin SDK (if you use other Firebase services like Auth, Firestore, etc.)
if firebase_credentials_dict and not firebase_admin._apps:
    cred = credentials.Certificate(firebase_credentials_dict)
    firebase_admin.initialize_app(cred)
    print("Firebase Admin SDK initialized successfully.")

# 3. Configure django-storages to use Google Cloud Storage for all file uploads
DEFAULT_FILE_STORAGE = 'storages.backends.gcloud.GoogleCloudStorage'
GS_BUCKET_NAME = os.getenv('FIREBASE_STORAGE_BUCKET')

# 4. Explicitly set Google Cloud Storage credentials from the loaded dictionary
if firebase_credentials_dict:
    GS_CREDENTIALS = service_account.Credentials.from_service_account_info(firebase_credentials_dict)

# Optional: Set a default access level for uploaded files
GS_DEFAULT_ACL = 'publicRead'


# --- Third-Party App Settings ---
# --------------------------------------------------------------------------
# Django Rest Framework & JWT
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=1200),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

# CORS
CORS_ALLOWED_ORIGINS = [
    "https://qms-3lra.vercel.app",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://localhost:5173",
    "https://*.devtunnels.ms",
    "https://qms-2h5c.onrender.com",
    "http://69.62.80.202",
    "https://qms.nkprosales.com"
]


# --- Email Configuration ---
# --------------------------------------------------------------------------
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL')


# --- Other Project Settings ---
# --------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
QUOTATION_PREFIX = os.getenv('QUOTATION_PREFIX', 'QTN')
