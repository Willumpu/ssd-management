"""
异常样品管理模块
"""
import re
import os
from django.db import models
from django.utils import timezone
import datetime
from django_ckeditor_5.fields import CKEditor5Field
from fae.models import User, Customer


class AbnormalSampleGroup(models.Model):
    """异常样品组"""
    # 状态选项
    STATUS_CHOICES = [
        ('pending_analysis', '待分析'),
        ('retesting', '复测中'),
        ('resolved', '已解决'),
    ]
    
    # 优先级
    PRIORITY_CHOICES = [
        ('urgent', '紧急'),
        ('high', '高'),
        ('normal', '一般'),
    ]
    
    group_number = models.CharField('组编号', max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name='所属客户')
    project = models.ForeignKey('project.Project', on_delete=models.SET_NULL, verbose_name='所属项目',
                                 null=True, blank=True, related_name='abnormal_groups')
    status = models.CharField('当前状态', max_length=20, choices=STATUS_CHOICES, default='pending_analysis')
    priority = models.CharField('优先级', max_length=20, choices=PRIORITY_CHOICES, default='normal')
    solution = models.ForeignKey('solution.Solution', on_delete=models.SET_NULL, verbose_name='样品方案',
                                  null=True, blank=True, related_name='abnormal_groups')
    total_count = models.PositiveIntegerField('样品数量', default=0)
    abnormal_summary = models.CharField('异常概述', max_length=200, blank=True)
    abnormal_description = CKEditor5Field('异常描述')
    test_item = models.ForeignKey('testing.TestItem', on_delete=models.SET_NULL, verbose_name='所属测试',
                                   null=True, blank=True, related_name='abnormal_groups')
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, verbose_name='分析负责人',
                                  null=True, blank=True, related_name='assigned_groups')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='登记人', related_name='created_groups')
    created_at = models.DateTimeField('登记时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
    class Meta:
        verbose_name = '异常样品组'
        verbose_name_plural = '异常样品组'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.group_number} - {self.customer.customer_code}"
    
    def generate_group_number(self):
        """生成组编号：{customer_code}-G{三位序号}
        
        删除后重新创建会优先回补空缺编号
        """
        if not self.customer:
            return None
        
        existing_numbers = AbnormalSampleGroup.objects.filter(
            customer=self.customer
        ).values_list('group_number', flat=True)
        
        pattern = re.compile(rf'^{re.escape(self.customer.customer_code)}-G(\d+)$')
        existing_seqs = set()
        
        for num in existing_numbers:
            match = pattern.match(num)
            if match:
                existing_seqs.add(int(match.group(1)))
        
        # 从 1 开始找第一个不存在的序号（回补空缺）
        seq = 1
        while seq in existing_seqs:
            seq += 1
        
        return f"{self.customer.customer_code}-G{seq:03d}"
    
    def save(self, *args, **kwargs):
        is_new = not self.pk
        if is_new:
            new_group_number = self.generate_group_number()
            if new_group_number:
                self.group_number = new_group_number
        super().save(*args, **kwargs)


class AbnormalSample(models.Model):
    """异常样品管理"""
    # 日志获取选项
    LOG_CHOICES = [
        ('fw_running', 'FW Running Log'),
        ('fw_nlog', 'FW Nlog'),
        ('fw_info', 'FW Info'),
        ('fw_power_on', 'FW Power On Log'),
        ('fw_memory_dump', 'FW Memory Dump'),
        ('rdt_running', 'RDT Running Log'),
        ('rdt_all_flush', 'RDT All Flush Log'),
        ('rdt_detail', 'RDT Detail'),
    ]
    
    # 状态选项
    STATUS_CHOICES = [
        ('pending_analysis', '待分析'),
        ('retesting', '复测中'),
        ('resolved', '已解决'),
    ]
    
    # 优先级
    PRIORITY_CHOICES = [
        ('urgent', '紧急'),
        ('high', '高'),
        ('normal', '一般'),
    ]
    
    sample_number = models.CharField('样品编号', max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name='所属客户')
    project = models.ForeignKey('project.Project', on_delete=models.SET_NULL, verbose_name='所属项目',
                                 null=True, blank=True, related_name='abnormal_samples')
    status = models.CharField('当前状态', max_length=20, choices=STATUS_CHOICES, default='pending_analysis')
    priority = models.CharField('优先级', max_length=20, choices=PRIORITY_CHOICES, default='normal')
    solution = models.ForeignKey('solution.Solution', on_delete=models.SET_NULL, verbose_name='样品方案',
                                  null=True, blank=True, related_name='abnormal_samples')
    logs_collected = models.JSONField('日志获取', default=list, blank=True,
                                       help_text='选择的日志类型列表')
    abnormal_summary = models.CharField('异常概述', max_length=200, blank=True)
    abnormal_description = CKEditor5Field('异常描述')
    test_item = models.ForeignKey('testing.TestItem', on_delete=models.SET_NULL, verbose_name='所属测试',
                                   null=True, blank=True, related_name='abnormal_samples')
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, verbose_name='分析负责人',
                                  null=True, blank=True, related_name='assigned_abnormals')
    group = models.ForeignKey(AbnormalSampleGroup, on_delete=models.CASCADE, verbose_name='所属组',
                               null=True, blank=True, related_name='samples')
    is_edited_individually = models.BooleanField('是否单独编辑过', default=False)
    resolved_at = models.DateTimeField('解决时间', null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='登记人', related_name='created_abnormals')
    created_at = models.DateTimeField('登记时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
    class Meta:
        verbose_name = '异常样品'
        verbose_name_plural = '异常样品'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.sample_number} - {self.customer.customer_code}"
    
    def generate_sample_number(self):
        """生成样品编号: 客户编号-XXX
        
        规则：
        1. 格式：{customer_code}-{序号:03d}
        2. 删除后重新创建会优先回补空缺编号
        3. 无空缺时取最大序号+1
        """
        if not self.customer:
            return None
        
        # 获取该客户所有现有编号，提取序号
        existing_numbers = AbnormalSample.objects.filter(
            customer=self.customer
        ).values_list('sample_number', flat=True)
        
        pattern = re.compile(rf'^{re.escape(self.customer.customer_code)}-(\d+)$')
        existing_seqs = set()
        
        for num in existing_numbers:
            match = pattern.match(num)
            if match:
                existing_seqs.add(int(match.group(1)))
        
        # 从 1 开始找第一个不存在的序号（回补空缺）
        seq = 1
        while seq in existing_seqs:
            seq += 1
        
        return f"{self.customer.customer_code}-{seq:03d}"
    
    def save(self, *args, **kwargs):
        # 检查是否是新记录
        is_new = not self.pk
        
        # 如果是已有记录，检查客户是否变更
        if not is_new:
            try:
                old_instance = AbnormalSample.objects.get(pk=self.pk)
                old_customer = old_instance.customer
                customer_changed = old_customer != self.customer
            except AbnormalSample.DoesNotExist:
                customer_changed = False
        else:
            customer_changed = False
        
        # 新记录或客户变更时，重新生成编号
        if is_new or customer_changed:
            # 先生成新编号
            new_sample_number = self.generate_sample_number()
            if new_sample_number:
                self.sample_number = new_sample_number
        
        super().save(*args, **kwargs)


class TestRecordEntry(models.Model):
    """测试记录条目（用于异常样品）"""
    abnormal_sample = models.ForeignKey(AbnormalSample, on_delete=models.CASCADE, 
                                         verbose_name='异常样品', related_name='test_records')
    record_time = models.DateTimeField('记录时间', default=timezone.now)
    content = CKEditor5Field('记录内容')
    operator = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='记录人')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    
    class Meta:
        verbose_name = '测试记录条目'
        verbose_name_plural = '测试记录条目'
        ordering = ['-record_time']
    
    def __str__(self):
        return f"{self.abnormal_sample.sample_number} - {self.record_time.strftime('%Y-%m-%d %H:%M')}"


def abnormal_log_upload_path(instance, filename):
    """按 样品/类型/[文件夹]/文件名 组织目录，文件名由调用方决定"""
    now = timezone.now()
    base_path = f"abnormal/logs/{now:%Y/%m}"
    sample = instance.abnormal_sample

    if instance.folder_name:
        return f"{base_path}/{sample.sample_number}/{instance.log_type}/{instance.folder_name}/{filename}"
    return f"{base_path}/{sample.sample_number}/{instance.log_type}/{filename}"


class AbnormalLogFile(models.Model):
    """异常样品日志文件"""
    LOG_TYPE_CHOICES = [
        ('fw_running', 'FW Running Log'),
        ('fw_nlog', 'FW Nlog'),
        ('fw_info', 'FW Info'),
        ('fw_power_on', 'FW Power On Log'),
        ('fw_memory_dump', 'FW Memory Dump'),
        ('rdt_running', 'RDT Running Log'),
        ('rdt_all_flush', 'RDT All Flush Log'),
        ('rdt_detail', 'RDT Detail'),
        ('other', '其他'),
    ]
    
    abnormal_sample = models.ForeignKey(AbnormalSample, on_delete=models.CASCADE, 
                                         verbose_name='异常样品', related_name='log_files')
    log_type = models.CharField('日志类型', max_length=20, choices=LOG_TYPE_CHOICES)
    folder_name = models.CharField('文件夹名', max_length=255, blank=True, default='')
    file = models.FileField('日志文件', upload_to=abnormal_log_upload_path, max_length=500, blank=True, null=True)
    file_url = models.URLField('日志文件URL', max_length=500, blank=True, null=True)
    description = models.CharField('描述', max_length=200, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='上传人')
    uploaded_at = models.DateTimeField('上传时间', auto_now_add=True)
    
    class Meta:
        verbose_name = '日志文件'
        verbose_name_plural = '日志文件'
        ordering = ['-uploaded_at']
    
    @property
    def filename(self):
        """文件名（不含路径），兼容模板"""
        import os
        if self.file_url:
            return os.path.basename(self.file_url)
        if self.file:
            return os.path.basename(self.file.name)
        return ''
    
    @property
    def size(self):
        """文件大小（字节），兼容模板"""
        if self.file_url:
            return 0  # OSS 文件大小暂不支持，可后续扩展
        if self.file:
            return self.file.size
        return 0
    
    def get_download_url(self, expiration=3600):
        """生成带签名的临时下载 URL（私有 Bucket 用）"""
        if self.file_url:
            from utils.oss import get_signed_url
            # file_url 格式: https://bucket.endpoint/logs/abnormal/...
            # 需要从 URL 中提取 OSS 路径
            path = self.file_url.split('/', 3)[3]  # 去掉 https://bucket.endpoint/
            return get_signed_url(path, expiration)
        if self.file:
            return self.file.url
        return ''
    
    def __str__(self):
        return f"{self.abnormal_sample.sample_number} - {self.get_log_type_display()}"


class AbnormalComment(models.Model):
    """异常样品评论"""
    abnormal_sample = models.ForeignKey(AbnormalSample, on_delete=models.CASCADE, verbose_name='异常样品', related_name='comments')
    content = CKEditor5Field('评论内容')
    author = models.ForeignKey('fae.User', on_delete=models.CASCADE, verbose_name='评论人')
    created_at = models.DateTimeField('评论时间', auto_now_add=True)
    
    class Meta:
        verbose_name = '异常样品评论'
        verbose_name_plural = '异常样品评论'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.abnormal_sample.sample_number} - {self.author.username}"


class AbnormalLog(models.Model):
    """异常样品操作日志"""
    # 状态选项 - 与AbnormalSample 保持一致
    STATUS_CHOICES = [
        ('pending_analysis', '待分析'),
        ('retesting', '复测中'),
        ('resolved', '已解决'),
    ]
    
    abnormal_sample = models.ForeignKey(AbnormalSample, on_delete=models.CASCADE, verbose_name='异常样品', related_name='logs')
    operator = models.ForeignKey('fae.User', on_delete=models.CASCADE, verbose_name='操作人')
    action = models.CharField('操作', max_length=200)
    old_status = models.CharField('原状态', max_length=20, blank=True)
    new_status = models.CharField('新状态', max_length=20, blank=True)
    comment = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('操作时间', auto_now_add=True)
    
    class Meta:
        verbose_name = '异常样品日志'
        verbose_name_plural = '异常样品日志'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.abnormal_sample.sample_number} - {self.action}"
    
    def get_status_display_name(self, status_code):
        """获取状态的中文显示名称"""
        status_map = dict(self.STATUS_CHOICES)
        return status_map.get(status_code, status_code)
    
    def get_old_status_display(self):
        """获取原状态的中文显示名称"""
        return self.get_status_display_name(self.old_status)
    
    def get_new_status_display(self):
        """获取新状态的中文显示名称"""
        return self.get_status_display_name(self.new_status)
