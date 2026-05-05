"""
方案管理模块
"""
from django.db import models
from django.utils import timezone
import datetime
from fae.models import User
from django_ckeditor_5.fields import CKEditor5Field


class ControllerModel(models.Model):
    """主控型号管理"""
    name = models.CharField('主控型号', max_length=50, unique=True)
    description = models.TextField('型号描述', blank=True)
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
    class Meta:
        verbose_name = '主控型号'
        verbose_name_plural = '主控型号'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class FlashModel(models.Model):
    """Flash型号管理"""
    name = models.CharField('Flash型号', max_length=50, unique=True)
    description = models.TextField('型号描述', blank=True)
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
    class Meta:
        verbose_name = 'Flash型号'
        verbose_name_plural = 'Flash型号'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class PCBModel(models.Model):
    """PCB型号管理"""
    name = models.CharField('PCB型号', max_length=50, unique=True)
    description = models.TextField('型号描述', blank=True)
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
    class Meta:
        verbose_name = 'PCB型号'
        verbose_name_plural = 'PCB型号'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Solution(models.Model):
    """方案管理"""
    # 状态选项
    STATUS_CHOICES = [
        ('alpha', 'Alpha'),
        ('beta', 'Beta'),
        ('release', 'Release'),
    ]
    
    solution_number = models.CharField('方案编号', max_length=100, unique=True, editable=False)
    project = models.ForeignKey('project.Project', on_delete=models.SET_NULL, verbose_name='所属项目',
                                 null=True, blank=True, related_name='solutions')
    controller_model = models.ForeignKey(ControllerModel, on_delete=models.PROTECT, verbose_name='主控型号')
    flash_model = models.ForeignKey(FlashModel, on_delete=models.PROTECT, verbose_name='Flash型号')
    flash_count = models.PositiveIntegerField('Flash数量', default=0)
    pcb_models = models.ManyToManyField(PCBModel, verbose_name='PCB型号', blank=True)
    software_version = models.CharField('软件版本', max_length=50)
    release_date = models.DateField('发布日期')
    status = models.CharField('状态', max_length=10, choices=STATUS_CHOICES, default='alpha')
    
    # 附件
    software_file = models.FileField('软件', upload_to='solutions/software/%Y/%m/', blank=True, null=True,
                                      help_text='ZIP格式附件')
    production_data = models.FileField('生产资料', upload_to='solutions/production/%Y/%m/', blank=True, null=True,
                                        help_text='ZIP格式附件')
    test_report = models.FileField('测试报告', upload_to='solutions/reports/%Y/%m/', blank=True, null=True,
                                    help_text='PDF格式附件')
    
    description = CKEditor5Field('方案描述', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建人', related_name='created_solutions')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
    class Meta:
        verbose_name = '方案'
        verbose_name_plural = '方案'
        ordering = ['-release_date', '-created_at']
    
    def __str__(self):
        return self.solution_number
    
    def generate_solution_number(self):
        """生成方案编号: 主控型号_Flash型号xFlash数量_软件版本_发布日期"""
        date_str = self.release_date.strftime('%Y%m%d')
        return f"{self.controller_model.name}_{self.flash_model.name}x{self.flash_count}_{self.software_version}_{date_str}"
    
    def save(self, *args, **kwargs):
        # 如果是新建或关键字段变更，重新生成编号
        if not self.solution_number or self.pk:
            # 先保存以获取日期（如果是新记录）
            if not self.pk:
                super().save(*args, **kwargs)
            self.solution_number = self.generate_solution_number()
            # 保存所有字段（包括状态等）
            super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)
    
    def get_status_display_class(self):
        """获取状态显示样式"""
        status_classes = {
            'alpha': 'bg-red-500/20 text-red-400 border border-red-500/30',
            'beta': 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
            'release': 'bg-green-500/20 text-green-400 border border-green-500/30',
        }
        return status_classes.get(self.status, 'bg-slate-700 text-slate-400')
    
    def get_pcb_models_display(self):
        """获取PCB型号显示文本"""
        pcbs = self.pcb_models.all()
        if pcbs:
            return ', '.join([p.name for p in pcbs])
        return "未选择"


class SolutionComment(models.Model):
    """方案评论"""
    solution = models.ForeignKey(Solution, on_delete=models.CASCADE, verbose_name='方案', related_name='comments')
    content = CKEditor5Field('评论内容')
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='评论人')
    created_at = models.DateTimeField('评论时间', auto_now_add=True)
    
    class Meta:
        verbose_name = '方案评论'
        verbose_name_plural = '方案评论'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.solution.solution_number} - {self.author.username}"


class SolutionLog(models.Model):
    """方案操作日志"""
    STATUS_CHOICES = [
        ('alpha', 'Alpha'),
        ('beta', 'Beta'),
        ('release', 'Release'),
    ]
    
    solution = models.ForeignKey(Solution, on_delete=models.CASCADE, verbose_name='方案', related_name='logs')
    operator = models.ForeignKey('fae.User', on_delete=models.CASCADE, verbose_name='操作人')
    action = models.CharField('操作', max_length=200)
    old_status = models.CharField('原状态', max_length=10, blank=True)
    new_status = models.CharField('新状态', max_length=10, blank=True)
    comment = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('操作时间', auto_now_add=True)
    
    class Meta:
        verbose_name = '方案日志'
        verbose_name_plural = '方案日志'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.solution.solution_number} - {self.action}"
    
    def get_old_status_display(self):
        """获取原状态显示名称"""
        status_dict = dict(self.STATUS_CHOICES)
        return status_dict.get(self.old_status, self.old_status)
    
    def get_new_status_display(self):
        """获取新状态显示名称"""
        status_dict = dict(self.STATUS_CHOICES)
        return status_dict.get(self.new_status, self.new_status)
