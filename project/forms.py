from django import forms
from .models import Project
from fae.models import Customer


class ProjectForm(forms.ModelForm):
    """项目表单"""
    class Meta:
        model = Project
        fields = ['name', 'customer', 'status', 'phase', 'sample_total_quantity', 'current_yield', 'yield_type', 'description']
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
            'phase': forms.Select(
                attrs={'class': 'bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-amber-500 w-full'}
            ),
            'sample_total_quantity': forms.NumberInput(
                attrs={'class': 'bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-amber-500 w-full', 'min': 0}
            ),
            'current_yield': forms.NumberInput(
                attrs={'class': 'bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-amber-500 w-full', 'min': 0, 'max': 100, 'step': '0.01'}
            ),
            'yield_type': forms.Select(
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
