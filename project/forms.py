from django import forms
from .models import Project
from fae.models import Customer


class ProjectForm(forms.ModelForm):
    """项目表单"""
    class Meta:
        model = Project
        fields = ['name', 'customer', 'status', 'description']
        widgets = {
            'name': forms.TextInput(
                attrs={'class': 'bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-amber-500 w-full', 'placeholder': '项目名称'}
            ),
            'customer': forms.Select(
                attrs={'class': 'bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-amber-500 w-full'}
            ),
            'status': forms.Select(
                attrs={'class': 'bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-amber-500 w-full'}
            ),
            'description': forms.Textarea(
                attrs={'rows': 4, 'class': 'bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-amber-500 w-full', 'placeholder': '项目描述（可选）'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer'].queryset = Customer.objects.all().order_by('customer_code')
        self.fields['customer'].required = False
