"""
研发需求管理模块
"""
from django.db import models
from django.utils import timezone
import datetime
from fae.models import User
from django_ckeditor_5.fields import CKEditor5Field


class RDRequirement(models.Model):
    """研发需求管理"""
    # 需求类型
    REQUIREMENT_TYPE_CHOICES = [
        ('hardware', '硬件需求'),
        ('software', '软件需求'),
        ('flash_debug', '颗粒调试'),
    ]
    
    # 优先级
    PRIORITY_CHOICES = [
        ('p0', 'P0 - 阻塞性问题'),
        ('p1', 'P1 - 重要需求'),
        ('p2', 'P2 - 一般优先'),
    ]
    
    # 状态
    STATUS_CHOICES = [
        ('rd_confirming', '研发确认中'),
        ('customer_confirming', '客户确认中'),
        ('in_progress', '进行中'),
        ('paused', '暂停中'),
        ('customer_verifying', '客户验证中'),
        ('archived', '已归档'),
    ]
    
    # 延期风险
    DELAY_RISK_CHOICES = [
        ('low', '低'),
        ('medium', '中'),
        ('high', '高'),
    ]
    
    requirement_number = models.CharField('需求编号', max_length=20, unique=True, editable=False)
    project = models.ForeignKey('project.Project', on_delete=models.SET_NULL, verbose_name='所属项目',
                                 null=True, blank=True, related_name='rd_requirements')
    assignee = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='负责人',
                                  related_name='assigned_requirements', 
                                  limit_choices_to={'role__in': ['rd', 'rd_leader']})
    requirement_type = models.CharField('需求类型', max_length=20, choices=REQUIREMENT_TYPE_CHOICES)
    priority = models.CharField('优先级', max_length=10, choices=PRIORITY_CHOICES, default='p2')
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='rd_confirming')
    title = models.CharField('需求标题', max_length=200)
    description = CKEditor5Field('需求描述')
    report_date = models.DateField('截至/汇报日期')
    
    # 进度时间
    start_date = models.DateField('开始时间', null=True, blank=True)
    end_date = models.DateField('截止时间', null=True, blank=True)
    
    # 延期风险
    delay_risk = models.CharField('延期风险', max_length=10, choices=DELAY_RISK_CHOICES, default='low')
    delay_reason = CKEditor5Field('延期原因', blank=True)
    
    # Jira编号
    jira_number = models.CharField('Jira编号', max_length=50, blank=True)
    
    # 关联信息
    related_customer = models.ForeignKey('fae.Customer', on_delete=models.SET_NULL, 
                                          verbose_name='关联客户', null=True, blank=True,
                                          related_name='rd_requirements')
    related_fae_task = models.ForeignKey('fae.FAETask', on_delete=models.SET_NULL,
                                          verbose_name='关联FAE任务', null=True, blank=True,
                                          related_name='rd_requirements')
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建人', 
                                    related_name='created_requirements')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
    class Meta:
        verbose_name = '研发需求'
        verbose_name_plural = '研发需求'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.requirement_number} - {self.title}"
    
    def generate_requirement_number(self):
        """生成需求编号 RD-YYMMDD-XXX"""
        today = datetime.date.today()
        date_str = today.strftime('%y%m%d')
        prefix = f"RD-{date_str}"
        
        last_req = RDRequirement.objects.filter(requirement_number__startswith=prefix).order_by('-requirement_number').first()
        if last_req:
            last_num = int(last_req.requirement_number.split('-')[-1])
            new_num = last_num + 1
        else:
            new_num = 1
        return f"{prefix}-{new_num:03d}"
    
    def save(self, *args, **kwargs):
        if not self.requirement_number:
            self.requirement_number = self.generate_requirement_number()
        super().save(*args, **kwargs)
    
    def get_latest_progress(self):
        """获取最新进展"""
        latest = self.progress_logs.first()
        if latest:
            content = latest.content[:50] + '...' if len(latest.content) > 50 else latest.content
            return content
        return "暂无进展"
    
    def get_latest_progress_percent(self):
        """获取最新进度百分比"""
        latest = self.progress_logs.first()
        if latest:
            return latest.progress_percent
        return 0
    
    def calculate_time_progress(self):
        """计算时间进度百分比，基于开始时间、截止时间和当前时间"""
        if not self.start_date or not self.end_date:
            return 0
        
        today = datetime.date.today()
        start_date = self.start_date
        end_date = self.end_date
        
        # 如果还未开始
        if today < start_date:
            return 0
        
        # 如果已经超过截止日期
        if today >= end_date:
            return 100
        
        # 计算进度
        total_days = (end_date - start_date).days
        if total_days <= 0:
            return 100
        
        elapsed_days = (today - start_date).days
        progress = int((elapsed_days / total_days) * 100)
        
        return min(progress, 100)
    
    def get_time_progress_display(self):
        """获取时间进度显示信息"""
        progress = self.calculate_time_progress()
        
        if not self.start_date or not self.end_date:
            return {'percent': 0, 'display': '未设置时间', 'color': 'bg-slate-500'}
        
        today = datetime.date.today()
        if today < self.start_date:
            return {'percent': 0, 'display': '尚未开始', 'color': 'bg-blue-500'}
        elif today > self.end_date:
            return {'percent': 100, 'display': '已超期', 'color': 'bg-red-500'}
        else:
            return {'percent': progress, 'display': f'{progress}%', 'color': 'bg-green-500'}
    
    def is_delay_risk_high_or_medium(self):
        """检查延期风险是否为中或高"""
        return self.delay_risk in ['medium', 'high']
    
    def get_delay_risk_display_class(self):
        """获取延期风险显示样式"""
        risk_classes = {
            'low': 'bg-green-500/20 text-green-400 border border-green-500/30',
            'medium': 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
            'high': 'bg-red-500/20 text-red-400 border border-red-500/30',
        }
        return risk_classes.get(self.delay_risk, 'bg-slate-500/20 text-slate-400')
    
    def get_status_display_class(self):
        """获取状态显示样式"""
        status_classes = {
            'rd_confirming': 'bg-purple-500/20 text-purple-400 border border-purple-500/30',
            'customer_confirming': 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
            'in_progress': 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
            'paused': 'bg-red-500/20 text-red-400 border border-red-500/30',
            'customer_verifying': 'bg-orange-500/20 text-orange-400 border border-orange-500/30',
            'archived': 'bg-green-500/20 text-green-400 border border-green-500/30',
        }
        return status_classes.get(self.status, 'bg-slate-500/20 text-slate-400')


class RequirementProgress(models.Model):
    """需求进展记录"""
    requirement = models.ForeignKey(RDRequirement, on_delete=models.CASCADE,
                                     verbose_name='需求', related_name='progress_logs')
    progress_date = models.DateField('汇报日期', default=timezone.now)
    content = CKEditor5Field('进展内容')
    progress_percent = models.PositiveIntegerField('进度百分比', default=0)
    reported_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='汇报人')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    
    class Meta:
        verbose_name = '需求进展记录'
        verbose_name_plural = '需求进展记录'
        ordering = ['-progress_date', '-created_at']
    
    def __str__(self):
        return f"{self.requirement.requirement_number} - {self.progress_date}"


class RequirementAttachment(models.Model):
    """需求附件"""
    requirement = models.ForeignKey(RDRequirement, on_delete=models.CASCADE,
                                     verbose_name='需求', related_name='attachments')
    file = models.FileField('附件', upload_to='requirements/attachments/%Y/%m/')
    description = models.CharField('描述', max_length=200, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='上传人')
    uploaded_at = models.DateTimeField('上传时间', auto_now_add=True)
    
    class Meta:
        verbose_name = '需求附件'
        verbose_name_plural = '需求附件'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.requirement.requirement_number} - {self.file.name}"


class RequirementComment(models.Model):
    """需求评论"""
    requirement = models.ForeignKey(RDRequirement, on_delete=models.CASCADE, verbose_name='需求', related_name='comments')
    content = CKEditor5Field('评论内容')
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='评论人')
    created_at = models.DateTimeField('评论时间', auto_now_add=True)
    
    class Meta:
        verbose_name = '需求评论'
        verbose_name_plural = '需求评论'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.requirement.requirement_number} - {self.author.username}"


class RequirementLog(models.Model):
    """需求操作日志"""
    STATUS_CHOICES = [
        ('not_started', '未开始'),
        ('in_progress', '进行中'),
        ('verification', '验证中'),
        ('archived', '已归档'),
    ]
    
    requirement = models.ForeignKey(RDRequirement, on_delete=models.CASCADE, verbose_name='需求', related_name='logs')
    operator = models.ForeignKey('fae.User', on_delete=models.CASCADE, verbose_name='操作人')
    action = models.CharField('操作', max_length=200)
    old_status = models.CharField('原状态', max_length=20, blank=True)
    new_status = models.CharField('新状态', max_length=20, blank=True)
    comment = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('操作时间', auto_now_add=True)
    
    class Meta:
        verbose_name = '需求操作日志'
        verbose_name_plural = '需求操作日志'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.requirement.requirement_number} - {self.action}"
    
    def get_status_display_name(self, status):
        """获取状态的中文显示名称"""
        status_dict = dict(self.STATUS_CHOICES)
        return status_dict.get(status, status)
    
    def get_old_status_display(self):
        """获取原状态的中文显示"""
        return self.get_status_display_name(self.old_status)
    
    def get_new_status_display(self):
        """获取新状态的中文显示"""
        return self.get_status_display_name(self.new_status)
