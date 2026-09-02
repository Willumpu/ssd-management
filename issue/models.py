"""
问题单管理模块
记录问题从发现到解决的全过程
"""
import datetime
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django_ckeditor_5.fields import CKEditor5Field


class Issue(models.Model):
    """问题单"""
    # 问题单状态
    STATUS_CHOICES = [
        ('pending', '未处理'),
        ('processing', '处理中'),
        ('closed', '已关闭'),
    ]

    # 优先级
    PRIORITY_CHOICES = [
        ('p0', 'P0'),
        ('p1', 'P1'),
        ('p2', 'P2'),
        ('p3', 'P3'),
    ]

    issue_number = models.CharField('问题单编号', max_length=20, unique=True, editable=False)
    project = models.ForeignKey(
        'project.Project', on_delete=models.CASCADE, verbose_name='所属项目',
        related_name='issues'
    )
    solution = models.ForeignKey(
        'solution.Solution', on_delete=models.CASCADE, verbose_name='关联方案',
        related_name='issues'
    )
    submitter = models.ForeignKey(
        'fae.User', on_delete=models.CASCADE, verbose_name='提交人',
        related_name='submitted_issues', limit_choices_to={'role__in': ['fae', 'fae_leader']}
    )
    priority = models.CharField('优先级', max_length=10, choices=PRIORITY_CHOICES, default='p1')
    jira_number = models.CharField('Jira编号', max_length=50, blank=True, default='')
    summary = models.CharField('问题概述', max_length=200, default='')
    abnormal_description = CKEditor5Field('异常描述')

    status = models.CharField('问题单状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    closed_at = models.DateTimeField('关闭时间', null=True, blank=True)
    created_at = models.DateTimeField('提交时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '问题单'
        verbose_name_plural = '问题单'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.issue_number} - {self.project}"

    def generate_issue_number(self):
        """生成问题单编号: ISS-YYMMDD-XXX"""
        today = datetime.date.today()
        date_str = today.strftime('%y%m%d')
        prefix = f"ISS-{date_str}"

        last_issue = Issue.objects.filter(issue_number__startswith=prefix).order_by('-issue_number').first()
        if last_issue:
            last_num = int(last_issue.issue_number.split('-')[-1])
            new_num = last_num + 1
        else:
            new_num = 1
        return f"{prefix}-{new_num:03d}"

    def save(self, *args, **kwargs):
        if not self.issue_number:
            self.issue_number = self.generate_issue_number()
        if self.status == 'closed' and not self.closed_at:
            self.closed_at = timezone.now()
        elif self.status != 'closed':
            self.closed_at = None
        super().save(*args, **kwargs)

    def get_status_display_class(self):
        """获取状态显示样式"""
        status_classes = {
            'pending': 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
            'processing': 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
            'closed': 'bg-green-500/20 text-green-400 border border-green-500/30',
        }
        return status_classes.get(self.status, 'bg-slate-700 text-slate-400')

    def get_priority_display_class(self):
        """获取优先级显示样式"""
        classes = {
            'p0': 'bg-red-500/20 text-red-400 border border-red-500/30',
            'p1': 'bg-orange-500/20 text-orange-400 border border-orange-500/30',
            'p2': 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
            'p3': 'bg-slate-500/20 text-slate-400 border border-slate-500/30',
        }
        return classes.get(self.priority, 'bg-slate-700 text-slate-400')


class IssueSolutionRecord(models.Model):
    """问题解决记录

    一个问题单可以有多个“问题解决”记录。
    每个记录内可以包含：排查记录、异常样品、根因结果、解决方案、验证记录。
    """
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, verbose_name='问题单', related_name='solution_records')
    created_by = models.ForeignKey('fae.User', on_delete=models.CASCADE, verbose_name='创建人')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '问题解决记录'
        verbose_name_plural = '问题解决记录'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.issue.issue_number} - 解决记录"


class IssueSolutionDetail(models.Model):
    """问题解决记录明细"""
    DETAIL_TYPE_CHOICES = [
        ('troubleshooting', '排查记录'),
        ('root_cause', '根因结果'),
        ('solution', '解决方案'),
        ('verification', '验证记录'),
    ]

    solution_record = models.ForeignKey(
        IssueSolutionRecord, on_delete=models.CASCADE, verbose_name='所属解决记录',
        related_name='details'
    )
    detail_type = models.CharField('明细类型', max_length=20, choices=DETAIL_TYPE_CHOICES)
    content = models.TextField('内容', blank=True)
    test_item = models.ForeignKey(
        'testing.TestItem', on_delete=models.SET_NULL, verbose_name='关联测试项（旧）',
        null=True, blank=True, related_name='solution_details_legacy'
    )
    test_items = models.ManyToManyField(
        'testing.TestItem', verbose_name='关联测试项',
        blank=True, related_name='solution_details'
    )
    abnormal_sample = models.ForeignKey(
        'abnormal.AbnormalSample', on_delete=models.SET_NULL, verbose_name='关联异常样品（旧）',
        null=True, blank=True, related_name='solution_details_legacy'
    )
    created_by = models.ForeignKey('fae.User', on_delete=models.CASCADE, verbose_name='记录人')
    created_at = models.DateTimeField('记录时间', auto_now_add=True)

    class Meta:
        verbose_name = '问题解决明细'
        verbose_name_plural = '问题解决明细'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.solution_record} - {self.get_detail_type_display()}"

    def clean(self):
        super().clean()
        if self.detail_type in ['troubleshooting', 'root_cause', 'solution', 'verification']:
            if not self.content.strip():
                raise ValidationError(f'{self.get_detail_type_display()}必须填写内容')


class IssueLog(models.Model):
    """问题单操作日志"""
    STATUS_CHOICES = [
        ('pending', '未处理'),
        ('processing', '处理中'),
        ('closed', '已关闭'),
    ]

    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, verbose_name='问题单', related_name='logs')
    operator = models.ForeignKey('fae.User', on_delete=models.CASCADE, verbose_name='操作人')
    action = models.CharField('操作', max_length=200)
    old_status = models.CharField('原状态', max_length=20, blank=True)
    new_status = models.CharField('新状态', max_length=20, blank=True)
    comment = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('操作时间', auto_now_add=True)

    class Meta:
        verbose_name = '问题单日志'
        verbose_name_plural = '问题单日志'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.issue.issue_number} - {self.action}"

    def get_status_display_name(self, status_code):
        """获取状态中文名称"""
        status_map = dict(self.STATUS_CHOICES)
        return status_map.get(status_code, status_code)

    def get_old_status_display(self):
        return self.get_status_display_name(self.old_status)

    def get_new_status_display(self):
        return self.get_status_display_name(self.new_status)
