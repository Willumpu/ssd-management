"""
研发需求表单
"""
from django import forms
from django_ckeditor_5.widgets import CKEditor5Widget
from .models import RDRequirement, RequirementComment, RequirementProgress


class RDRequirementForm(forms.ModelForm):
    """研发需求表单"""
    class Meta:
        model = RDRequirement
        fields = ['project', 'title', 'requirement_type', 'description', 'priority', 
                  'status', 'assignee', 'report_date', 'start_date', 'end_date',
                  'delay_risk', 'delay_reason', 'jira_number', 'related_customer', 'related_fae_task']
        widgets = {
            'description': CKEditor5Widget(config_name='default'),
            'delay_reason': CKEditor5Widget(config_name='default'),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        delay_risk = cleaned_data.get('delay_risk')
        delay_reason = cleaned_data.get('delay_reason')
        
        # 如果延期风险为中或高，必须填写延期原因
        if delay_risk in ['medium', 'high']:
            if not delay_reason or delay_reason.strip() == '':
                self.add_error('delay_reason', '延期风险为中或高时，必须填写延期原因')
        
        return cleaned_data


class RequirementCommentForm(forms.ModelForm):
    """研发需求评论表单"""
    class Meta:
        model = RequirementComment
        fields = ['content']
        widgets = {
            'content': CKEditor5Widget(config_name='comment'),
        }


class RequirementProgressForm(forms.ModelForm):
    """研发需求进展表单"""
    content = forms.CharField(
        label='进展内容',
        widget=CKEditor5Widget(config_name='default'),
        required=False
    )
    
    class Meta:
        model = RequirementProgress
        fields = ['content']
