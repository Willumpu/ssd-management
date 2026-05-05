from django.apps import AppConfig


class SampleShipmentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sample_shipment'
    verbose_name = '样品物料寄送管理'
