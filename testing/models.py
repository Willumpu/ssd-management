"""
测试跟踪管理模块
"""
from django.db import models
from django.utils import timezone
import datetime
from fae.models import User, Customer
from django_ckeditor_5.fields import CKEditor5Field


class TestItem(models.Model):
    """测试项管理"""
    # 测试内容选项
    TEST_CONTENT_CHOICES = [
        ('rdt', 'RDT'),
        ('burn_in', 'BurnInTest'),
        ('retention', 'Retention'),
        ('rebooter', 'Rebooter'),
        ('sleeper', 'Sleeper'),
        ('apl', 'APL'),
        ('sorting', 'Sorting'),
        ('performance', '性能测试'),
    ]
    
    # 测试状态
    TEST_STATUS_CHOICES = [
        ('not_started', '未开始'),
        ('in_progress', '进行中'),
        ('completed', '已结束'),
    ]
    
    test_number = models.CharField('测试项编号', max_length=20, unique=True, editable=False)
    tracker = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='跟踪人',
                                 related_name='tracked_tests', limit_choices_to={'role__in': ['fae', 'fae_leader']})
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name='所属客户')
    project = models.ForeignKey('project.Project', on_delete=models.SET_NULL, verbose_name='所属项目',
                                 null=True, blank=True, related_name='test_items')
    status = models.CharField('测试状态', max_length=20, choices=TEST_STATUS_CHOICES, default='not_started')
    test_content = models.CharField('测试内容', max_length=20, choices=TEST_CONTENT_CHOICES)
    solution = models.ForeignKey('solution.Solution', on_delete=models.SET_NULL, verbose_name='测试方案',
                                  null=True, blank=True, related_name='test_items')
    total_samples = models.PositiveIntegerField('样品总数', default=0)
    passed_samples = models.PositiveIntegerField('通过数量', default=0)
    abnormal_samples_count = models.PositiveIntegerField('异常数量', default=0)
    start_date = models.DateTimeField('开始时间', null=True, blank=True)
    end_date = models.DateTimeField('结束时间', null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建人', related_name='created_tests')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
    class Meta:
        verbose_name = '测试项'
        verbose_name_plural = '测试项'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.test_number} - {self.get_test_content_display()}"
    
    def generate_test_number(self):
        """生成测试项编号 TEST-YYMMDD-XXX"""
        today = datetime.date.today()
        date_str = today.strftime('%y%m%d')
        prefix = f"TEST-{date_str}"
        
        last_test = TestItem.objects.filter(test_number__startswith=prefix).order_by('-test_number').first()
        if last_test:
            last_num = int(last_test.test_number.split('-')[-1])
            new_num = last_num + 1
        else:
            new_num = 1
        return f"{prefix}-{new_num:03d}"
    
    def save(self, *args, **kwargs):
        if not self.test_number:
            self.test_number = self.generate_test_number()
        super().save(*args, **kwargs)


class TestAbnormalRelation(models.Model):
    """测试与异常样品关联"""
    test_item = models.ForeignKey(TestItem, on_delete=models.CASCADE, verbose_name='测试项', related_name='abnormal_relations')
    abnormal_sample = models.ForeignKey('abnormal.AbnormalSample', on_delete=models.CASCADE, verbose_name='异常样品')
    created_at = models.DateTimeField('关联时间', auto_now_add=True)
    
    class Meta:
        verbose_name = '测试异常关联'
        verbose_name_plural = '测试异常关联'
        unique_together = ['test_item', 'abnormal_sample']
    
    def __str__(self):
        return f"{self.test_item.test_number} - {self.abnormal_sample.sample_number}"


class TestComment(models.Model):
    """测试评论"""
    test = models.ForeignKey(TestItem, on_delete=models.CASCADE, verbose_name='测试项', related_name='comments')
    content = CKEditor5Field('评论内容')
    author = models.ForeignKey('fae.User', on_delete=models.CASCADE, verbose_name='评论人')
    created_at = models.DateTimeField('评论时间', auto_now_add=True)
    
    class Meta:
        verbose_name = '测试评论'
        verbose_name_plural = '测试评论'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.test.test_number} - {self.author.username}"


class TestItemLog(models.Model):
    """测试项操作日志"""
    
    # 状态选项
    STATUS_CHOICES = [
        ('not_started', '未开始'),
        ('in_progress', '进行中'),
        ('completed', '已结束'),
    ]
    
    test_item = models.ForeignKey(TestItem, on_delete=models.CASCADE, verbose_name='测试项', related_name='logs')
    operator = models.ForeignKey('fae.User', on_delete=models.CASCADE, verbose_name='操作人')
    action = models.CharField('操作', max_length=200)
    old_status = models.CharField('原状态', max_length=20, blank=True)
    new_status = models.CharField('新状态', max_length=20, blank=True)
    comment = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('操作时间', auto_now_add=True)
    
    class Meta:
        verbose_name = '测试项日志'
        verbose_name_plural = '测试项日志'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.test_item.test_number} - {self.action}"
    
    def get_status_display_name(self, status):
        """获取状态的中文显示名称"""
        status_map = dict(self.STATUS_CHOICES)
        return status_map.get(status, status)
    
    def get_old_status_display(self):
        """获取原状态的中文显示名称"""
        return self.get_status_display_name(self.old_status)
    
    def get_new_status_display(self):
        """获取新状态的中文显示名称"""
        return self.get_status_display_name(self.new_status)
