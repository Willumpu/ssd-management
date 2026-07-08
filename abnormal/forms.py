"""
异常样品表单
"""
from django import forms
from django_ckeditor_5.widgets import CKEditor5Widget
from .models import AbnormalSample, AbnormalSampleGroup, AbnormalComment


class AbnormalSampleGroupForm(forms.ModelForm):
    """异常样品组表单"""
    total_count = forms.IntegerField(
        label='样品数量',
        min_value=1,
        max_value=1000,
        initial=1,
        help_text='创建组时自动生成对应数量的异常样品'
    )
    
    class Meta:
        model = AbnormalSampleGroup
        fields = ['customer', 'project', 'solution', 'abnormal_summary', 'abnormal_description', 'priority', 'status', 'assignee', 'test_item', 'total_count']
        widgets = {
            'abnormal_description': CKEditor5Widget(config_name='default'),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from fae.models import User
        from testing.models import TestItem
        from solution.models import Solution
        from fae.models import Customer
        from project.models import Project
        
        self.fields['assignee'].queryset = User.objects.filter(role__in=['fae', 'fae_leader'])
        self.fields['assignee'].required = False
        self.fields['customer'].queryset = Customer.objects.all().order_by('customer_code')
        self.fields['solution'].queryset = Solution.objects.all().order_by('-created_at')
        self.fields['solution'].required = False
        self.fields['project'].queryset = Project.objects.all().order_by('-created_at')
        self.fields['project'].required = False
        test_item_qs = TestItem.objects.filter(
            status__in=['not_started', 'in_progress']
        ).select_related('customer').order_by('-created_at')
        # 编辑模式下，确保当前关联的测试项也在 queryset 中
        if self.instance and self.instance.pk and self.instance.test_item:
            if not test_item_qs.filter(pk=self.instance.test_item.pk).exists():
                test_item_qs = TestItem.objects.filter(pk=self.instance.test_item.pk) | test_item_qs
        self.fields['test_item'].queryset = test_item_qs
        self.fields['test_item'].required = False
        self.fields['test_item'].empty_label = "请选择关联测试项（可选）"


class AbnormalSampleForm(forms.ModelForm):
    """异常样品表单"""
    class Meta:
        model = AbnormalSample
        fields = ['project', 'customer', 'test_item', 'abnormal_summary', 'abnormal_description', 'priority', 'assignee', 'solution']
        widgets = {
            'abnormal_description': CKEditor5Widget(config_name='default'),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 可选：限制测试项为进行中的项目
        from testing.models import TestItem
        # 获取当前已选择的测试项（如果有）
        current_test_item = self.initial.get('test_item') or self.instance.test_item if self.instance.pk else None
        
        # 查询进行中的测试项
        test_items = TestItem.objects.filter(
            status__in=['not_started', 'in_progress']
        ).select_related('customer').order_by('-created_at')
        
        # 如果有已选择的测试项但不在查询集中，添加到查询集
        if current_test_item and isinstance(current_test_item, TestItem):
            if not test_items.filter(pk=current_test_item.pk).exists():
                test_items = TestItem.objects.filter(
                    pk=current_test_item.pk
                ) | test_items
        
        self.fields['test_item'].queryset = test_items
        self.fields['test_item'].required = False
        self.fields['test_item'].empty_label = "请选择关联测试项（可选）"


class AbnormalCommentForm(forms.ModelForm):
    """异常样品评论表单"""
    class Meta:
        model = AbnormalComment
        fields = ['content']
        widgets = {
            'content': CKEditor5Widget(config_name='comment'),
        }
