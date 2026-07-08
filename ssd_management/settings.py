"""
SSD 主控厂商市场部管理平台 - Django 设置
"""

from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'p-X-am4xFTRaCtQJUOGMuNKpHfUh7k_OedkCtM0rnAXaq_RTUU-UvdHozVRo53ULs44'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # 第三方应用
    'django_ckeditor_5',
    # 自定义应用
    'project',
    'fae',
    'testing',
    'abnormal',
    'solution',
    'rd_requirement',
    'sample_shipment',
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

ROOT_URLCONF = 'ssd_management.urls'

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

WSGI_APPLICATION = 'ssd_management.wsgi.application'


# Database - 使用 SQLite 便于本地演示
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'zh-hans'

TIME_ZONE = 'Asia/Shanghai'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# 日志文件本地缓存目录（OSS 文件首次查看时下载到此处）
LOG_CACHE_DIR = BASE_DIR / 'media' / 'cache' / 'logs'

# 阿里云 OSS 配置（手动上传方案）
ALIBABA_OSS = {
    'ACCESS_KEY_ID': os.environ.get('ALIBABA_OSS_ACCESS_KEY_ID', ''),
    'ACCESS_KEY_SECRET': os.environ.get('ALIBABA_OSS_ACCESS_KEY_SECRET', ''),
    'ENDPOINT': 'oss-cn-shenzhen.aliyuncs.com',    # 华南1(深圳) Endpoint
    'BUCKET_NAME': 'ssd-logs',
}

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# 登录配置
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# 自定义用户模型
AUTH_USER_MODEL = 'fae.User'
# CKEditor 5 配置
# 自定义 CSS 样式路径
CKEDITOR_5_CUSTOM_CSS = 'css/ckeditor5-dark.css'

CKEDITOR_5_CONFIGS = {
    'default': {
        'toolbar': ['heading', '|', 'bold', 'italic', 'underline', 'strikethrough',
                   '|', 'fontSize', 'fontFamily', 'fontColor', 'fontBackgroundColor',
                   '|', 'alignment', 'outdent', 'indent',
                   '|', 'bulletedList', 'numberedList', 'todoList',
                   '|', 'link', 'imageUpload', 'mediaEmbed', 'blockQuote', 'insertTable', 'codeBlock',
                   '|', 'undo', 'redo', 'findAndReplace', 'selectAll',
                   '|', 'sourceEditing'],
        'height': '300px',
        'width': '100%',
        'image': {
            'toolbar': ['imageTextAlternative', '|', 'imageStyle:alignLeft', 
                       'imageStyle:alignCenter', 'imageStyle:alignRight', '|',
                       'imageStyle:full', 'imageStyle:side'],
            'styles': ['full', 'side', 'alignLeft', 'alignCenter', 'alignRight'],
        },
        'table': {
            'contentToolbar': ['tableColumn', 'tableRow', 'mergeTableCells', 
                              'tableProperties', 'tableCellProperties'],
        },
        'fontFamily': {
            'options': ['default', 'Arial', 'Times New Roman', 'Verdana', 'Helvetica', 'Georgia', 
                       'Courier New', 'Comic Sans MS', 'Trebuchet MS', 'Impact',
                       '微软雅黑', '宋体', '黑体', '楷体'],
            'supportAllValues': True,
        },
        'fontSize': {
            'options': [8, 10, 12, 14, 'default', 18, 20, 22, 24, 28, 32, 36, 48],
            'supportAllValues': True,
        },
    },
    'comment': {
        'toolbar': ['bold', 'italic', 'underline', '|', 
                   'bulletedList', 'numberedList', '|', 
                   'link', 'imageUpload', '|', 'undo', 'redo'],
        'height': '200px',
        'width': '100%',
        'image': {
            'toolbar': ['imageTextAlternative', '|', 'imageStyle:alignLeft', 
                       'imageStyle:alignCenter', 'imageStyle:alignRight'],
            'styles': ['alignLeft', 'alignCenter', 'alignRight'],
        },
    },
}

# 文件上传权限: staff/authenticated/any
CKEDITOR_5_FILE_UPLOAD_PERMISSION = "authenticated"
# 使用 Django 配置的语言
CKEDITOR_5_USER_LANGUAGE = True
