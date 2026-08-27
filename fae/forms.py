"""
FAE 表单
"""
from django import forms
from django_ckeditor_5.widgets import CKEditor5Widget
from .models import FAETask, FAETaskComment
from project.models import ProductionPlan


class FAETaskForm(forms.ModelForm):
    """FAE任务表单"""
    production_plan = forms.ModelChoiceField(
        queryset=ProductionPlan.objects.none(),
        required=True,
        label='生产方案',
        empty_label='请选择生产方案',
        widget=forms.Select(attrs={
            'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-blue-500'
        })
    )

    class Meta:
        model = FAETask
        fields = ['project', 'production_plan', 'assignee', 'customer', 'task_type', 'summary', 'description', 'test_items']
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
