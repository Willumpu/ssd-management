"""
测试跟踪管理模块
"""
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
import datetime
from fae.models import User, Customer
from django_ckeditor_5.fields import CKEditor5Field


class TestContent(models.Model):
    """测试内容（可在后台管理）"""
    code = models.CharField('编码', max_length=30, unique=True)
    name = models.CharField('名称', max_length=50)
    is_active = models.BooleanField('启用', default=True)
    order = models.PositiveIntegerField('排序', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '测试内容'
        verbose_name_plural = '测试内容'
        ordering = ['order', 'id']

    def __str__(self):
        return self.name


class TestItem(models.Model):
    """测试项管理"""
    # 保留旧选项常量用于兼容与数据迁移
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
    test_content = models.ForeignKey(
        TestContent, on_delete=models.PROTECT, verbose_name='测试内容',
        null=True, blank=True, related_name='test_items'
    )
    solution = models.ForeignKey('solution.Solution', on_delete=models.SET_NULL, verbose_name='测试方案',
                                  null=True, blank=True, related_name='test_items')
    sample_source = models.CharField('样品来源', max_length=100, blank=True)
    total_samples = models.PositiveIntegerField('样品总数', default=0)
    passed_samples = models.PositiveIntegerField('通过数量', default=0)
    abnormal_samples_count = models.PositiveIntegerField('异常数量', default=0)
    testing_samples = models.PositiveIntegerField('测试中数量', default=0)
    retesting_samples = models.PositiveIntegerField('复测中数量', default=0)
    
    # 桑基图流转关系
    BRANCH_TYPE_CHOICES = [
        ('initial', '初始测试'),
        ('passed', '通过分支'),
        ('failed', '失败/异常分支'),
    ]
    source_tests = models.ManyToManyField('self', symmetrical=False, verbose_name='来源测试项',
                                           blank=True, related_name='derived_tests')
    branch_type = models.CharField('分支类型', max_length=20, choices=BRANCH_TYPE_CHOICES,
                                    blank=True, default='')
    source_sankey_node = models.ForeignKey(
        'SankeyNode', on_delete=models.SET_NULL, verbose_name='来源桑基图节点',
        null=True, blank=True, related_name='sourced_test_items'
    )
    
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
        return f"{self.test_number} - {self.test_content.name if self.test_content else '-'}"
    
    def get_test_content_display(self):
        """兼容旧模板/代码的显示方法"""
        return self.test_content.name if self.test_content else '-'
    
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
    
    def clean(self):
        super().clean()
        total = self.total_samples or 0
        passed = self.passed_samples or 0
        abnormal = self.abnormal_samples_count or 0
        testing = self.testing_samples or 0
        retesting = self.retesting_samples or 0
        counted = passed + abnormal + testing + retesting
        if counted > total:
            raise ValidationError(
                f'通过数量({passed}) + 异常数量({abnormal}) + 测试中数量({testing}) + 复测中数量({retesting}) '
                f'为 {counted}，不能超过样品总数({total})'
            )
    
    def save(self, *args, **kwargs):
        self.clean()
        if not self.test_number:
            self.test_number = self.generate_test_number()
        super().save(*args, **kwargs)


class TestParameterDefinition(models.Model):
    """测试参数定义（后台可管理）"""
    DATA_TYPE_CHOICES = [
        ('integer', '整数'),
        ('float', '浮点数'),
        ('string', '字符串'),
    ]
    
    name = models.CharField('参数名称', max_length=50)
    param_key = models.CharField('参数标识', max_length=50, unique=True)
    unit = models.CharField('单位', max_length=20, blank=True)
    data_type = models.CharField('数据类型', max_length=10, choices=DATA_TYPE_CHOICES, default='string')
    default_value = models.CharField('默认值', max_length=100, blank=True)
    description = models.TextField('参数说明', blank=True)
    is_active = models.BooleanField('是否启用', default=True)
    order = models.PositiveIntegerField('排序', default=0)
    
    class Meta:
        verbose_name = '测试参数定义'
        verbose_name_plural = '测试参数定义'
        ordering = ['order', 'id']
    
    def __str__(self):
        if self.unit:
            return f"{self.name} ({self.unit})"
        return self.name


class TestItemParameter(models.Model):
    """测试项参数值"""
    test_item = models.ForeignKey(TestItem, on_delete=models.CASCADE, verbose_name='测试项', related_name='parameters')
    parameter = models.ForeignKey(TestParameterDefinition, on_delete=models.CASCADE, verbose_name='参数定义')
    value = models.CharField('参数值', max_length=100, blank=True)
    
    class Meta:
        verbose_name = '测试项参数值'
        verbose_name_plural = '测试项参数值'
        unique_together = ['test_item', 'parameter']
        ordering = ['parameter__order', 'parameter__id']
    
    def __str__(self):
        return f"{self.test_item.test_number} - {self.parameter.name}: {self.value}"


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


class AbnormalReason(models.Model):
    """异常原因分类（可配置）"""
    name = models.CharField('异常原因', max_length=100, unique=True)
    description = models.TextField('原因说明', blank=True)
    is_active = models.BooleanField('是否启用', default=True)
    order = models.PositiveIntegerField('排序', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    
    class Meta:
        verbose_name = '异常原因'
        verbose_name_plural = '异常原因'
        ordering = ['order', 'id']
    
    def __str__(self):
        return self.name


class TestItemAbnormalAnalysis(models.Model):
    """测试项异常样品分析记录"""
    test_item = models.ForeignKey(TestItem, on_delete=models.CASCADE, verbose_name='测试项', related_name='abnormal_analyses')
    reason = models.ForeignKey(AbnormalReason, on_delete=models.PROTECT, verbose_name='异常原因')
    quantity = models.PositiveIntegerField('数量', default=0)
    description = models.TextField('详细说明', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='分析人', related_name='abnormal_analyses')
    sankey_node = models.ForeignKey(
        'SankeyNode',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='关联桑基图节点',
        related_name='abnormal_analyses'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
    class Meta:
        verbose_name = '异常样品分析'
        verbose_name_plural = '异常样品分析'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.test_item.test_number} - {self.reason.name}: {self.quantity}"
    
    def clean(self):
        super().clean()
        if self.quantity <= 0:
            raise ValidationError('数量必须大于0')
        if self.test_item_id:
            total_abnormal = self.test_item.abnormal_samples_count or 0
            existing = TestItemAbnormalAnalysis.objects.filter(test_item=self.test_item)
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            current_total = existing.aggregate(total=models.Sum('quantity'))['total'] or 0
            if current_total + self.quantity > total_abnormal:
                remaining = max(total_abnormal - current_total, 0)
                raise ValidationError(
                    f'该测试项异常样品总数为 {total_abnormal}，已分析 {current_total}，还可添加 {remaining}，'
                    f'当前数量 {self.quantity} 超出限制'
                )


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


class SankeyNode(models.Model):
    """桑基图节点（样品状态批次）"""
    NODE_TYPE_CHOICES = [
        ('initial', '初始'),
        ('pass', '通过'),
        ('fail', '失败'),
        ('subcategory', '子分类'),
        ('abnormal_category', '异常分类'),
        ('merged', '合流'),
    ]
    
    fae_task = models.ForeignKey('fae.FAETask', on_delete=models.CASCADE, verbose_name='所属FAE任务',
                                  related_name='sankey_nodes')
    label = models.CharField('节点标签', max_length=100)
    quantity = models.PositiveIntegerField('样品数量', default=0)
    node_type = models.CharField('节点类型', max_length=20, choices=NODE_TYPE_CHOICES, default='initial')
    parent_nodes = models.ManyToManyField('self', symmetrical=False, blank=True, verbose_name='父节点',
                                           related_name='child_nodes')
    test_item = models.ForeignKey(TestItem, on_delete=models.SET_NULL, verbose_name='关联测试项',
                                   null=True, blank=True, related_name='sankey_nodes')
    category_reason = models.CharField('分类原因', max_length=100, blank=True)
    custom_y = models.FloatField('自定义Y坐标', null=True, blank=True, help_text='用户手动拖拽的Y位置，为空则自动布局')
    abnormal_samples = models.ManyToManyField(
        'abnormal.AbnormalSample',
        blank=True,
        verbose_name='关联异常样品',
        related_name='sankey_nodes'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    
    class Meta:
        verbose_name = '桑基图节点'
        verbose_name_plural = '桑基图节点'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.label} ({self.quantity}片)"


class SankeyEdge(models.Model):
    """桑基图流（测试操作）"""
    fae_task = models.ForeignKey('fae.FAETask', on_delete=models.CASCADE, verbose_name='所属FAE任务',
                                  related_name='sankey_edges')
    label = models.CharField('流标签', max_length=100)
    source_node = models.ForeignKey(SankeyNode, on_delete=models.CASCADE, verbose_name='源节点',
                                     related_name='outgoing_edges')
    target_node = models.ForeignKey(SankeyNode, on_delete=models.CASCADE, verbose_name='目标节点',
                                     related_name='incoming_edges')
    quantity = models.PositiveIntegerField('流转数量', default=0)
    test_item = models.ForeignKey(TestItem, on_delete=models.SET_NULL, verbose_name='关联测试项',
                                   null=True, blank=True, related_name='sankey_edges')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    
    class Meta:
        verbose_name = '桑基图流'
        verbose_name_plural = '桑基图流'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.source_node.label} --{self.label}({self.quantity})--> {self.target_node.label}"
