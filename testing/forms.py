"""
测试跟踪表单
"""
from django import forms
from django_ckeditor_5.widgets import CKEditor5Widget
from .models import TestItem, TestComment


class TestItemForm(forms.ModelForm):
    """测试项表单 - 用于更新，包含所有字段"""
    class Meta:
        model = TestItem
        fields = ['project', 'test_content', 'customer', 'tracker', 'solution',
                  'total_samples', 'passed_samples', 'abnormal_samples_count',
                  'start_date', 'end_date', 'status']


class TestItemCreateForm(forms.ModelForm):
    """测试项创建表单 - 创建时不需要填写状态、通过数量、异常数量"""
    class Meta:
        model = TestItem
        fields = ['project', 'test_content', 'customer', 'tracker', 'solution',
                  'total_samples', 'start_date', 'end_date']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 如果从 FAE 任务跳转过来，自动填充客户
        if self.initial.get('customer'):
            self.fields['customer'].initial = self.initial.get('customer')


class TestCommentForm(forms.ModelForm):
    """测试评论表单"""
    class Meta:
        model = TestComment
        fields = ['content']
        widgets = {
            'content': CKEditor5Widget(config_name='comment'),
        }
