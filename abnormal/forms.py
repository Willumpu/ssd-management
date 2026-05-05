"""
异常样品表单
"""
from django import forms
from django_ckeditor_5.widgets import CKEditor5Widget
from .models import AbnormalSample, AbnormalComment


class AbnormalSampleForm(forms.ModelForm):
    """异常样品表单"""
    class Meta:
        model = AbnormalSample
        fields = ['project', 'customer', 'test_item', 'abnormal_description', 'priority', 'assignee', 'solution']
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
