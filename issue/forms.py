"""问题单表单"""
from django import forms
from .models import Issue, IssueSolutionRecord, IssueSolutionDetail


class IssueForm(forms.ModelForm):
    class Meta:
        model = Issue
        fields = ['project', 'solution', 'priority', 'status', 'abnormal_description']
        widgets = {
            'abnormal_description': forms.Textarea(attrs={
                'rows': 6,
                'class': 'w-full rounded-lg border border-slate-600 bg-slate-800/70 text-slate-200 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500'
            }),
            'project': forms.Select(attrs={
                'class': 'w-full rounded-lg border border-slate-600 bg-slate-800/70 text-slate-200 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500'
            }),
            'solution': forms.Select(attrs={
                'class': 'w-full rounded-lg border border-slate-600 bg-slate-800/70 text-slate-200 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500'
            }),
            'priority': forms.Select(attrs={
                'class': 'w-full rounded-lg border border-slate-600 bg-slate-800/70 text-slate-200 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full rounded-lg border border-slate-600 bg-slate-800/70 text-slate-200 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # priority/status 不强制前端必填，clean 方法会回退默认值
        self.fields['priority'].required = False
        self.fields['status'].required = False
        self.fields['project'].empty_label = None
        self.fields['solution'].empty_label = None

    def clean_priority(self):
        return self.cleaned_data.get('priority') or 'p1'

    def clean_status(self):
        return self.cleaned_data.get('status') or 'pending'


class IssueSolutionRecordForm(forms.ModelForm):
    """问题解决记录无需用户填写字段，由系统自动生成"""
    class Meta:
        model = IssueSolutionRecord
        fields = []


class IssueSolutionDetailForm(forms.ModelForm):
    class Meta:
        model = IssueSolutionDetail
        fields = ['detail_type', 'content', 'test_items']
        widgets = {
            'detail_type': forms.HiddenInput(),
            'content': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full rounded-lg border border-slate-600 bg-slate-800/70 text-slate-200 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500',
                'placeholder': '请输入内容...',
            }),
            'test_items': forms.SelectMultiple(attrs={
                'class': 'w-full rounded-lg border border-slate-600 bg-slate-800/70 text-slate-200 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['content'].required = False

    def clean(self):
        cleaned_data = super().clean()
        detail_type = cleaned_data.get('detail_type')
        content = cleaned_data.get('content', '') or ''

        if detail_type in ['troubleshooting', 'root_cause', 'solution', 'verification']:
            if not content.strip():
                self.add_error('content', f'{self.instance.get_detail_type_display() if self.instance.pk else "该类型"}必须填写内容')

        return cleaned_data
