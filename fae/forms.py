"""
FAE 表单
"""
from django import forms
from django_ckeditor_5.widgets import CKEditor5Widget
from .models import FAETask, FAETaskComment


class FAETaskForm(forms.ModelForm):
    """FAE任务表单"""
    class Meta:
        model = FAETask
        fields = ['project', 'assignee', 'customer', 'task_type', 'summary', 'description', 'test_items']
        widgets = {
            'description': CKEditor5Widget(config_name='default'),
        }


class FAETaskCommentForm(forms.ModelForm):
    """FAE任务评论表单"""
    class Meta:
        model = FAETaskComment
        fields = ['content']
        widgets = {
            'content': CKEditor5Widget(config_name='comment'),
        }
