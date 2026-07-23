"""
项目管理模块
统筹 FAE任务、测试跟踪、异常样品、方案、研发需求、样品物料
"""
import datetime
from django.db import models
# from fae.models import User, Customer  # 使用字符串引用避免循环导入


class Project(models.Model):
    """项目"""
    STATUS_CHOICES = [
        ('active', '进行中'),
        ('completed', '已完成'),
        ('on_hold', '已暂停'),
    ]

    PHASE_CHOICES = [
        ('import', '导入阶段'),
        ('pilot', '试产阶段'),
        ('mass_production', '量产阶段'),
    ]

    YIELD_TYPE_CHOICES = [
        ('estimated', '估算良率'),
        ('calculated', '计算良率'),
    ]

    project_number = models.CharField('项目编号', max_length=20, unique=True, editable=False)
    name = models.CharField('项目名称', max_length=200)
    customer = models.ForeignKey(
        'fae.Customer', on_delete=models.SET_NULL, verbose_name='关联客户',
        null=True, blank=True, related_name='projects'
    )
    status = models.CharField('项目状态', max_length=20, choices=STATUS_CHOICES, default='active')
    phase = models.CharField('项目阶段', max_length=20, choices=PHASE_CHOICES, default='import')
    sample_total_quantity = models.PositiveIntegerField('样品总数量', default=0, blank=True)
    current_yield = models.DecimalField('当前良率', max_digits=5, decimal_places=2, null=True, blank=True,
                                        help_text='单位：%')
    yield_type = models.CharField('良率类型', max_length=20, choices=YIELD_TYPE_CHOICES, blank=True)
    description = models.TextField('项目描述', blank=True)
    created_by = models.ForeignKey(
        'fae.User', on_delete=models.CASCADE, verbose_name='创建人',
        related_name='created_projects'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '项目'
        verbose_name_plural = '项目'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.project_number} - {self.name}"

    def generate_project_number(self):
        prefix = "PRJ"
        last = Project.objects.filter(
            project_number__startswith=prefix
        ).order_by('-project_number').first()
        if last:
            last_num = int(last.project_number.split('-')[-1])
            new_num = last_num + 1
        else:
            new_num = 1
        return f"{prefix}-{new_num:04d}"

    def save(self, *args, **kwargs):
        if not self.project_number:
            self.project_number = self.generate_project_number()
        super().save(*args, **kwargs)

    def get_related_counts(self):
        """获取各模块关联数量"""
        return {
            'fae_tasks': self.fae_tasks.count(),
            'test_items': self.test_items.count(),
            'abnormal_samples': self.abnormal_samples.count(),
            'solutions': self.solutions.count(),
            'rd_requirements': self.rd_requirements.count(),
            'sample_materials': self.sample_materials.count(),
            'issues': self.issues.count(),
        }

    def get_total_items(self):
        """获取关联条目总数"""
        counts = self.get_related_counts()
        return sum(counts.values())

    def get_current_yield_display(self):
        """格式化当前良率显示"""
        if self.current_yield is None:
            return '-'
        suffix = ''
        if self.yield_type:
            suffix = f"（{self.get_yield_type_display()}）"
        return f"{self.current_yield}%{suffix}"
