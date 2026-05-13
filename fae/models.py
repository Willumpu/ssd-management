"""
FAE 任务管理模块
"""
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django_ckeditor_5.fields import CKEditor5Field
import datetime


class User(AbstractUser):
    """自定义用户模型"""
    ROLE_CHOICES = [
        ('fae', 'FAE工程师'),
        ('fae_leader', 'FAE主管'),
        ('rd', '研发工程师'),
        ('rd_leader', '研发主管'),
        ('warehouse', '仓库管理员'),
        ('admin', '管理员'),
    ]
    
    role = models.CharField('角色', max_length=20, choices=ROLE_CHOICES, default='fae')
    nickname = models.CharField('昵称', max_length=50, blank=True)
    phone = models.CharField('电话', max_length=20, blank=True)
    department = models.CharField('部门', max_length=50, blank=True)
    avatar = models.ImageField('头像', upload_to='avatars/%Y/%m/', blank=True, null=True)
    
    class Meta:
        verbose_name = '用户'
        verbose_name_plural = '用户'
    
    def __str__(self):
        name = self.first_name or self.username
        return f"{name} ({self.get_role_display()})"
    
    def is_fae_leader(self):
        return self.role == 'fae_leader'
    
    def is_rd_leader(self):
        return self.role == 'rd_leader'
    
    def is_admin_role(self):
        """检查是否是管理员角色"""
        return self.role == 'admin'
    
    def has_all_permissions(self):
        """检查是否有所有权限（超级管理员）"""
        return self.is_superuser or self.is_staff or self.role == 'admin'


class Customer(models.Model):
    """客户信息 - 仅保留客户编号"""
    customer_code = models.CharField('客户编号', max_length=10, unique=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    
    class Meta:
        verbose_name = '客户'
        verbose_name_plural = '客户'
        ordering = ['customer_code']
    
    def __str__(self):
        return self.customer_code


class FAETask(models.Model):
    """FAE任务管理"""
    # 任务类型
    TASK_TYPE_CHOICES = [
        ('test_tracking', '测试跟踪'),
        ('abnormal_tracking', '异常跟踪'),
        ('customer_comm', '客户沟通'),
        ('first_piece_test', '首件测试'),
    ]
    
    # 任务状态
    TASK_STATUS_CHOICES = [
        ('not_started', '未开始'),
        ('in_progress', '进行中'),
        ('pending_review', '待审核'),
        ('completed', '已结束'),
        ('paused', '暂停中'),
    ]
    
    # 审核结果
    REVIEW_RESULT_CHOICES = [
        ('pending', '待审核'),
        ('passed', '通过'),
        ('rejected', '不通过'),
    ]
    
    task_number = models.CharField('任务编号', max_length=20, unique=True, editable=False)
    assignee = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='负责人', 
                                  related_name='fae_tasks', limit_choices_to={'role__in': ['fae', 'fae_leader']})
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name='所属客户')
    project = models.ForeignKey('project.Project', on_delete=models.SET_NULL, verbose_name='所属项目',
                                 null=True, blank=True, related_name='fae_tasks')
    task_type = models.CharField('任务类型', max_length=20, choices=TASK_TYPE_CHOICES)
    status = models.CharField('任务状态', max_length=20, choices=TASK_STATUS_CHOICES, default='not_started')
    summary = models.CharField('任务概述', max_length=200, help_text='任务的简短概述或标题')
    description = CKEditor5Field('任务描述', blank=True, null=True)
    test_items = models.ManyToManyField('testing.TestItem', verbose_name='测试项',
                                         blank=True, related_name='fae_tasks')
    result = CKEditor5Field('任务结论', blank=True, null=True)
    review_result = models.CharField('审核结果', max_length=20, choices=REVIEW_RESULT_CHOICES, default='pending')
    review_comment = models.TextField('审核意见', blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, verbose_name='审核人',
                                     null=True, blank=True, related_name='reviewed_tasks')
    reviewed_at = models.DateTimeField('审核时间', null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建人', related_name='created_fae_tasks')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
    class Meta:
        verbose_name = 'FAE任务'
        verbose_name_plural = 'FAE任务'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.task_number} - {self.customer}"
    
    def generate_task_number(self):
        """生成任务编号: FAE-YYMMDD-XXX"""
        today = datetime.date.today()
        date_str = today.strftime('%y%m%d')
        prefix = f"FAE-{date_str}"
        
        # 获取当天最后一个编号
        last_task = FAETask.objects.filter(task_number__startswith=prefix).order_by('-task_number').first()
        if last_task:
            last_num = int(last_task.task_number.split('-')[-1])
            new_num = last_num + 1
        else:
            new_num = 1
        return f"{prefix}-{new_num:03d}"
    
    def save(self, *args, **kwargs):
        if not self.task_number:
            self.task_number = self.generate_task_number()
        super().save(*args, **kwargs)


class FAETaskLog(models.Model):
    """FAE任务操作日志"""
    STATUS_CHOICES = [
        ('not_started', '未开始'),
        ('in_progress', '进行中'),
        ('pending_review', '待审核'),
        ('completed', '已结束'),
        ('paused', '暂停中'),
    ]
    
    task = models.ForeignKey(FAETask, on_delete=models.CASCADE, verbose_name='任务', related_name='logs')
    operator = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='操作人')
    action = models.CharField('操作', max_length=200)
    old_status = models.CharField('原状态', max_length=20, blank=True)
    new_status = models.CharField('新状态', max_length=20, blank=True)
    comment = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('操作时间', auto_now_add=True)
    
    class Meta:
        verbose_name = 'FAE任务日志'
        verbose_name_plural = 'FAE任务日志'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.task.task_number} - {self.action}"
    
    def get_status_display_name(self, status_code):
        """获取状态中文名"""
        status_dict = dict(self.STATUS_CHOICES)
        return status_dict.get(status_code, status_code)
    
    def get_old_status_display(self):
        """获取原状态中文名"""
        return self.get_status_display_name(self.old_status)
    
    def get_new_status_display(self):
        """获取新状态中文名"""
        return self.get_status_display_name(self.new_status)


class FAETaskComment(models.Model):
    """FAE任务评论"""
    task = models.ForeignKey(FAETask, on_delete=models.CASCADE, verbose_name='任务', related_name='comments')
    content = CKEditor5Field('评论内容')
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='评论人')
    created_at = models.DateTimeField('评论时间', auto_now_add=True)
    
    class Meta:
        verbose_name = 'FAE任务评论'
        verbose_name_plural = 'FAE任务评论'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.task.task_number} - {self.author.username}"


class LogAnalyzerKeyword(models.Model):
    """日志分析关键词配置"""
    name = models.CharField('关键词名称', max_length=100)
    pattern = models.CharField('匹配内容', max_length=500, help_text='支持普通文本或正则表达式')
    regex = models.BooleanField('是否正则', default=False)
    is_active = models.BooleanField('是否启用', default=True)
    order = models.PositiveIntegerField('排序', default=0, help_text='数字越小越靠前')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '日志分析关键词'
        verbose_name_plural = '日志分析关键词'
        ordering = ['order', 'id']

    def __str__(self):
        return self.name


class Notification(models.Model):
    """通知模型"""
    NOTIFICATION_TYPE_CHOICES = [
        ('task_updated', '任务更新'),
        ('task_commented', '任务评论'),
        ('task_status_changed', '状态变更'),
        ('task_reviewed', '任务审核'),
    ]
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='接收人', related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='发送人', related_name='sent_notifications')
    task = models.ForeignKey(FAETask, on_delete=models.CASCADE, verbose_name='相关任务', related_name='notifications')
    notification_type = models.CharField('通知类型', max_length=30, choices=NOTIFICATION_TYPE_CHOICES)
    title = models.CharField('标题', max_length=200)
    message = models.TextField('内容', blank=True)
    is_read = models.BooleanField('是否已读', default=False)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    
    class Meta:
        verbose_name = '通知'
        verbose_name_plural = '通知'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.recipient.username} - {self.title}"
