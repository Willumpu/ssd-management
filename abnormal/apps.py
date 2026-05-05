from django.apps import AppConfig


class AbnormalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'abnormal'
    verbose_name = '异常样品管理'
