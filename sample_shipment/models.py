"""
样品物料库存管理模块
"""
import datetime
from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from fae.models import User, Customer


class Warehouse(models.Model):
    """仓库"""
    WAREHOUSE_TYPE_CHOICES = [
        ('company', '公司仓库'),
        ('customer', '客户仓库'),
    ]

    code = models.CharField('仓库编码', max_length=30, unique=True)
    name = models.CharField('仓库名称', max_length=100)
    warehouse_type = models.CharField('仓库类型', max_length=20, choices=WAREHOUSE_TYPE_CHOICES)
    related_customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, verbose_name='关联客户',
        null=True, blank=True, related_name='warehouses'
    )
    is_active = models.BooleanField('启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '仓库'
        verbose_name_plural = '仓库'
        ordering = ['warehouse_type', 'code']

    def __str__(self):
        return self.name

    @classmethod
    def get_or_create_default_warehouses(cls):
        """获取或创建3个固定仓库：深圳办公室、苏州研发、客户处"""
        sz, _ = cls.objects.get_or_create(
            code='SZ',
            defaults={'name': '深圳办公室', 'warehouse_type': 'company'}
        )
        suzhou, _ = cls.objects.get_or_create(
            code='SUZHOU',
            defaults={'name': '苏州研发', 'warehouse_type': 'company'}
        )
        customer_wh, _ = cls.objects.get_or_create(
            code='CUSTOMER',
            defaults={'name': '客户处', 'warehouse_type': 'customer'}
        )
        return {'SZ': sz, 'SUZHOU': suzhou, 'CUSTOMER': customer_wh}


class SampleMaterial(models.Model):
    """物料/样品档案"""
    CATEGORY_CHOICES = [
        ('ssd', 'SSD样品'),
        ('board', '主板/PCB'),
        ('chip', '芯片/颗粒'),
        ('tool', '工具/设备'),
        ('other', '其他'),
    ]

    STATUS_CHOICES = [
        ('returned', '归还'),
        ('borrowed', '借用'),
        ('scrapped', '报废'),
        ('lost', '丢失'),
    ]

    material_number = models.CharField('物料编号', max_length=20, unique=True, editable=False)
    name = models.CharField('物料名称', max_length=100)
    project = models.ForeignKey('project.Project', on_delete=models.SET_NULL, verbose_name='所属项目',
                                 null=True, blank=True, related_name='sample_materials')
    category = models.CharField('类别', max_length=20, choices=CATEGORY_CHOICES, default='ssd')
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='returned')
    related_customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, verbose_name='归属方',
        null=True, blank=True, related_name='materials'
    )
    description = models.TextField('描述', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '物料档案'
        verbose_name_plural = '物料档案'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.material_number} - {self.name}"

    def generate_material_number(self):
        prefix = "MAT"
        last = SampleMaterial.objects.filter(
            material_number__startswith=prefix
        ).order_by('-material_number').first()
        if last:
            last_num = int(last.material_number.split('-')[-1])
            new_num = last_num + 1
        else:
            new_num = 1
        return f"{prefix}-{new_num:04d}"

    def save(self, *args, **kwargs):
        if not self.material_number:
            self.material_number = self.generate_material_number()
        super().save(*args, **kwargs)

    def get_stock_by_warehouse(self):
        """获取该物料在各仓库的库存"""
        stocks = {}
        for stock in self.stocks.select_related('warehouse'):
            stocks[stock.warehouse_id] = {
                'warehouse': stock.warehouse,
                'quantity': stock.quantity,
            }
        return stocks

    def get_total_stock(self):
        """获取总库存数量"""
        from django.db.models import Sum
        result = self.stocks.aggregate(total=Sum('quantity'))
        return result['total'] or 0


class WarehouseStock(models.Model):
    """仓库库存"""
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE,
        verbose_name='仓库', related_name='stocks'
    )
    material = models.ForeignKey(
        SampleMaterial, on_delete=models.CASCADE,
        verbose_name='物料', related_name='stocks'
    )
    quantity = models.PositiveIntegerField('数量', default=0)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '仓库库存'
        verbose_name_plural = '仓库库存'
        unique_together = ['warehouse', 'material']
        ordering = ['-quantity']

    def __str__(self):
        return f"{self.warehouse.name} - {self.material.name}: {self.quantity}"


class MaterialTransfer(models.Model):
    """物料流转/调拨记录"""
    transfer_number = models.CharField('调拨编号', max_length=20, unique=True, editable=False)
    material = models.ForeignKey(
        SampleMaterial, on_delete=models.CASCADE,
        verbose_name='物料', related_name='transfers'
    )
    from_warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE,
        verbose_name='来源仓库', related_name='outbound_transfers'
    )
    to_warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE,
        verbose_name='目标仓库', related_name='inbound_transfers'
    )
    quantity = models.PositiveIntegerField('数量', validators=[MinValueValidator(1)])
    transfer_date = models.DateTimeField('调拨日期', default=datetime.datetime.now)
    tracking_info = models.CharField('物流信息/快递单号', max_length=100, blank=True,
                                      help_text='可选，记录快递单号等辅助信息')
    operator = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name='操作人',
        related_name='transfers'
    )
    remark = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '物料流转记录'
        verbose_name_plural = '物料流转记录'
        ordering = ['-transfer_date', '-created_at']

    def __str__(self):
        return f"{self.transfer_number} - {self.material.name} ({self.from_warehouse.name} → {self.to_warehouse.name})"

    def generate_transfer_number(self):
        today = datetime.date.today()
        date_str = today.strftime('%y%m%d')
        prefix = f"TRF-{date_str}"
        last = MaterialTransfer.objects.filter(
            transfer_number__startswith=prefix
        ).order_by('-transfer_number').first()
        if last:
            last_num = int(last.transfer_number.split('-')[-1])
            new_num = last_num + 1
        else:
            new_num = 1
        return f"{prefix}-{new_num:03d}"

    def save(self, *args, **kwargs):
        if not self.transfer_number:
            self.transfer_number = self.generate_transfer_number()
        super().save(*args, **kwargs)

    def clean(self):
        if self.from_warehouse_id == self.to_warehouse_id:
            raise ValidationError({'to_warehouse': '来源仓库和目标仓库不能相同'})
