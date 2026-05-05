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

    project_number = models.CharField('项目编号', max_length=20, unique=True, editable=False)
    name = models.CharField('项目名称', max_length=200)
    customer = models.ForeignKey(
        'fae.Customer', on_delete=models.SET_NULL, verbose_name='关联客户',
        null=True, blank=True, related_name='projects'
    )
    status = models.CharField('项目状态', max_length=20, choices=STATUS_CHOICES, default='active')
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
        }

    def get_total_items(self):
        """获取关联条目总数"""
        counts = self.get_related_counts()
        return sum(counts.values())


class ActivityTimeline(models.Model):
    """项目活动/时间线"""
    ACTION_CHOICES = [
        ('create', '创建'),
        ('update', '更新'),
        ('delete', '删除'),
        ('status_change', '状态变更'),
        ('comment', '评论'),
        ('transfer', '调拨'),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, verbose_name='项目',
        related_name='activities'
    )
    actor = models.ForeignKey(
        'fae.User', on_delete=models.CASCADE, verbose_name='操作人',
        related_name='project_activities'
    )
    action = models.CharField('操作类型', max_length=20, choices=ACTION_CHOICES)
    module_type = models.CharField('模块类型', max_length=30)
    object_id = models.PositiveIntegerField('记录ID')
    title = models.CharField('标题', max_length=200)
    subtitle = models.CharField('副标题/概述', max_length=200, blank=True)
    description = models.TextField('描述', blank=True)
    created_at = models.DateTimeField('操作时间', auto_now_add=True)

    class Meta:
        verbose_name = '项目活动记录'
        verbose_name_plural = '项目活动记录'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.project.project_number} - {self.get_action_display()} {self.module_type}"

    def get_module_display_name(self):
        module_map = {
            'fae_task': 'FAE任务',
            'test_item': '测试跟踪',
            'abnormal_sample': '异常样品',
            'solution': '方案',
            'rd_requirement': '研发需求',
            'sample_material': '样品物料',
            'project': '项目',
        }
        return module_map.get(self.module_type, self.module_type)
