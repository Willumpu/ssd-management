"""
生产环境配置
"""
from .settings import *
import os

DEBUG = False
ALLOWED_HOSTS = ['47.106.23.59', 'localhost', '127.0.0.1']

# MySQL 数据库配置
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'ssd_management',
        'USER': 'ssd_user',
        'PASSWORD': 'xxy1112...',
        'HOST': 'localhost',
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }
}

# 静态文件
STATIC_ROOT = '/var/www/ssd_management/static/'
MEDIA_ROOT = '/var/www/ssd_management/media/'

# 安全设置
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# 缓存
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# 日志
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': '/var/log/ssd_management/django.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
    },
}
