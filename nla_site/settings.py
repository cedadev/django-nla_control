
# -*- coding: utf-8 -*-

import os


# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


DEBUG = True


# Read the secret key from a file
SECRET_KEY_FILE = '/home/vagrant/NLA/conf/secret_key.txt'
with open(SECRET_KEY_FILE) as f:
    SECRET_KEY = f.read().strip()


# Logging settings


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
        'django_extensions',
        'nla_control',
    ]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    ]

ROOT_URLCONF = 'nla_site.urls'

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

WSGI_APPLICATION = 'nla_site.wsgi.application'


# Database
DATABASES = {
        'default' : {
                                'ENGINE' : 'django.db.backends.postgresql',
                                            'HOST' : '/tmp',
                                            'ATOMIC_REQUESTS' : True,
                                            'NAME' : 'nla_control',
                        },
    }


# Authentication settings
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
LANGUAGE_CODE = 'en-gb'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = False


# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = '/var/www/static'


# Email
# Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
SERVER_EMAIL = DEFAULT_FROM_EMAIL = 'nla@nla.ceda.ac.uk'



# Put your custom settings here.
ALLOWED_HOSTS=["192.168.51.21",
               "192.168.51.21"]

# App specific settings file for the nla_control app
NLA_LOG_PATH = "/var/log/nla"
STORAGED_SLOTS = 5
MAX_SLOTS_PER_USER = 2

# NRM 06/12/2016 - set this variable to True to use a test version that uses a local disk
# store as an analogue for the NLA tape system
# This will need a Django server with the NLA system and cedaarchive app running on it
TEST_VERSION = False

# This is the url that contains the mappings between spots and logical paths
# NRM note - this URL will change when new cedaarchiveapp is deployed
CEDA_ARCAPP_BASE = 'http://cedaarchiveapp.ceda.ac.uk/cedaarchiveapp/'
CEDA_DOWNLOAD_CONF = CEDA_ARCAPP_BASE+'fileset/download_conf'

# This is the url that contains the mapping between the storage path and the spots
# NRM note - this URL will change when new cedaarchiveapp is deployed
STORAGE_PATHS_URL = CEDA_ARCAPP_BASE+'storage-d/spotlist?withpath'

# This is the url that contains the location of the api call to get the files which are marked "primary on tape"
ON_TAPE_URL = CEDA_ARCAPP_BASE+'fileset/primary_on_tape'

# host of storage-D retrieval
SD_HOST = 'ceda_sd-retrieval.fds.rl.ac.uk'
MIN_FILE_SIZE = 30 * 1024 * 1024 # (30 Mb)
TEST_VERSION = False
CHKSUMSDIR = "/datacentre/stats/storaged/chksums"
