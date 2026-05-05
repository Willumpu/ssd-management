"""
方案管理表单
"""
from django import forms
from django_ckeditor_5.widgets import CKEditor5Widget
from .models import Solution, SolutionComment


class SolutionForm(forms.ModelForm):
    """方案表单"""
    class Meta:
        model = Solution
        fields = ['project', 'controller_model', 'flash_model', 'pcb_models', 'flash_count',
                  'software_version', 'release_date', 'status', 'description',
                  'software_file', 'production_data', 'test_report']
        widgets = {
            'description': CKEditor5Widget(config_name='default'),
        }


class SolutionCommentForm(forms.ModelForm):
    """方案评论表单"""
    class Meta:
        model = SolutionComment
        fields = ['content']
        widgets = {
            'content': CKEditor5Widget(config_name='comment'),
        }
