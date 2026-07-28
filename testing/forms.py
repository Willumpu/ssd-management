"""
测试跟踪表单
"""
from django import forms
from django.db.models import Sum
from django_ckeditor_5.widgets import CKEditor5Widget
from .models import TestItem, TestComment, TestParameterDefinition, TestItemParameter, AbnormalReason, TestItemAbnormalAnalysis


def _add_dynamic_param_fields(form_instance):
    """为表单动态添加测试参数字段"""
    params = TestParameterDefinition.objects.filter(is_active=True).order_by('order', 'id')
    existing_values = {}
    if form_instance.instance and form_instance.instance.pk:
        existing_values = {
            p.parameter.param_key: p.value
            for p in TestItemParameter.objects.filter(test_item=form_instance.instance)
        }
    for param in params:
        field_key = f'param_{param.param_key}'
        label = f'{param.name}'
        if param.unit:
            label += f' ({param.unit})'
        initial = existing_values.get(param.param_key)
        if initial is None:
            initial = param.default_value or None
        if param.data_type == 'integer':
            form_instance.fields[field_key] = forms.IntegerField(
                label=label, required=False, initial=initial,
                widget=forms.NumberInput(attrs={'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-blue-500'})
            )
        elif param.data_type == 'float':
            form_instance.fields[field_key] = forms.FloatField(
                label=label, required=False, initial=initial,
                widget=forms.NumberInput(attrs={'step': '0.01', 'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-blue-500'})
            )
        else:
            form_instance.fields[field_key] = forms.CharField(
                label=label, required=False, initial=initial or '',
                widget=forms.TextInput(attrs={'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-blue-500'})
            )
    return params


class TestItemForm(forms.ModelForm):
    """测试项表单 - 用于更新，包含所有字段"""
    abnormal_group = forms.ModelChoiceField(
        label='关联异常样品组',
        queryset=None,
        required=False,
        empty_label='请选择异常样品组（可选）',
        help_text='选择后自动关联该组内所有异常样品，并为其添加测试记录'
    )
    abnormal_samples = forms.ModelMultipleChoiceField(
        label='关联异常样品',
        queryset=None,
        required=False,
        help_text='选择后直接关联异常样品，并为其添加测试记录'
    )
    
    class Meta:
        model = TestItem
        fields = ['project', 'test_content', 'customer', 'tracker', 'solution', 'sample_source',
                  'total_samples', 'passed_samples', 'abnormal_samples_count',
                  'testing_samples', 'retesting_samples',
                  'start_date', 'end_date', 'status']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from abnormal.models import AbnormalSampleGroup, AbnormalSample
        self.fields['abnormal_group'].queryset = AbnormalSampleGroup.objects.filter(
            status__in=['pending_analysis', 'retesting']
        ).select_related('customer').order_by('-created_at')
        # 编辑时包含已关联的异常样品
        queryset = AbnormalSample.objects.filter(
            status__in=['pending_analysis', 'retesting'],
        ).select_related('group', 'customer').order_by('-created_at')
        if self.instance and self.instance.pk:
            linked_ids = list(self.instance.abnormal_relations.values_list('abnormal_sample_id', flat=True))
            if linked_ids:
                queryset = (queryset | AbnormalSample.objects.filter(pk__in=linked_ids)).distinct()
        self.fields['abnormal_samples'].queryset = queryset
        self.fields['solution'].required = True
        self._param_defs = list(_add_dynamic_param_fields(self))


class TestItemCreateForm(forms.ModelForm):
    """测试项创建表单 - 创建时需要填写各状态样品数量，且总和必须等于样品总数"""
    abnormal_group = forms.ModelChoiceField(
        label='关联异常样品组',
        queryset=None,
        required=False,
        empty_label='请选择异常样品组（可选）',
        help_text='选择后自动关联该组内所有异常样品，并为其添加测试记录'
    )
    abnormal_samples = forms.ModelMultipleChoiceField(
        label='关联异常样品',
        queryset=None,
        required=False,
        help_text='选择后直接关联异常样品，并为其添加测试记录'
    )
    
    class Meta:
        model = TestItem
        fields = ['project', 'test_content', 'customer', 'tracker', 'solution', 'sample_source',
                  'total_samples', 'passed_samples', 'abnormal_samples_count',
                  'testing_samples', 'retesting_samples',
                  'start_date', 'end_date']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from abnormal.models import AbnormalSampleGroup, AbnormalSample
        self.fields['abnormal_group'].queryset = AbnormalSampleGroup.objects.filter(
            status__in=['pending_analysis', 'retesting']
        ).select_related('customer').order_by('-created_at')
        self.fields['abnormal_samples'].queryset = AbnormalSample.objects.filter(
            status__in=['pending_analysis', 'retesting'],
        ).select_related('group', 'customer').order_by('-created_at')
        # 如果从 FAE 任务跳转过来，自动填充客户
        if self.initial.get('customer'):
            self.fields['customer'].initial = self.initial.get('customer')
        self.fields['solution'].required = True
        self._param_defs = list(_add_dynamic_param_fields(self))


class TestCommentForm(forms.ModelForm):
    """测试评论表单"""
    class Meta:
        model = TestComment
        fields = ['content']
        widgets = {
            'content': CKEditor5Widget(config_name='comment'),
        }


class TestItemAbnormalAnalysisForm(forms.ModelForm):
    """测试项异常样品分析表单"""
    class Meta:
        model = TestItemAbnormalAnalysis
        fields = ['reason', 'quantity', 'description']
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-blue-500'
            }),
            'quantity': forms.NumberInput(attrs={
                'min': 1,
                'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-blue-500'
            }),
            'reason': forms.Select(attrs={
                'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-blue-500'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.test_item = kwargs.pop('test_item', None)
        super().__init__(*args, **kwargs)
        self.fields['reason'].queryset = AbnormalReason.objects.filter(is_active=True).order_by('order', 'name')
    
    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity') or 0
        if quantity <= 0:
            raise forms.ValidationError('数量必须大于0')
        
        test_item = self.test_item or (self.instance.test_item if self.instance else None)
        if test_item:
            total_abnormal = test_item.abnormal_samples_count or 0
            existing = TestItemAbnormalAnalysis.objects.filter(test_item=test_item)
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            current_total = existing.aggregate(total=Sum('quantity'))['total'] or 0
            remaining = max(total_abnormal - current_total, 0)
            if quantity > remaining:
                raise forms.ValidationError(
                    f'该测试项异常样品总数为 {total_abnormal}，已分析 {current_total}，还可添加 {remaining}。'
                )
        return quantity
