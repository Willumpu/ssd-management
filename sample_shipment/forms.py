"""
样品物料库存管理表单
"""
from django import forms
from .models import SampleMaterial, MaterialTransfer, Warehouse, WarehouseStock


class SampleMaterialForm(forms.ModelForm):
    """物料档案表单"""
    initial_warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.filter(is_active=True).order_by('code'),
        label='初始仓库',
        required=True,
        widget=forms.Select(
            attrs={'class': 'bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-amber-500 w-full'}
        )
    )
    initial_quantity = forms.IntegerField(
        label='初始数量',
        min_value=0,
        initial=0,
        required=True,
        widget=forms.NumberInput(
            attrs={'class': 'bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-amber-500 w-full', 'min': 0, 'placeholder': '放入初始仓库的数量'}
        )
    )

    class Meta:
        model = SampleMaterial
        fields = ['project', 'name', 'category', 'status', 'related_customer', 'description']
        widgets = {
            'name': forms.TextInput(
                attrs={'class': 'bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-amber-500 w-full', 'placeholder': '例如：SSD样品-128GB'}
            ),
            'category': forms.Select(
                attrs={'class': 'bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-amber-500 w-full'}
            ),
            'status': forms.Select(
                attrs={'class': 'bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-amber-500 w-full'}
            ),
            'related_customer': forms.Select(
                attrs={'class': 'bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-amber-500 w-full'}
            ),
            'description': forms.Textarea(
                attrs={'rows': 4, 'class': 'bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-amber-500 w-full', 'placeholder': '物料的详细描述（可选）'}
            ),
        }


class MaterialTransferForm(forms.ModelForm):
    """物料调拨/流转表单"""
    class Meta:
        model = MaterialTransfer
        fields = ['material', 'from_warehouse', 'to_warehouse', 'quantity', 'transfer_date', 'tracking_info', 'remark']
        widgets = {
            'material': forms.Select(
                attrs={'class': 'bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500 w-full'}
            ),
            'from_warehouse': forms.Select(
                attrs={'class': 'bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500 w-full'}
            ),
            'to_warehouse': forms.Select(
                attrs={'class': 'bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500 w-full'}
            ),
            'quantity': forms.NumberInput(
                attrs={'class': 'bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500 w-full', 'min': 1}
            ),
            'transfer_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500 w-full'}
            ),
            'tracking_info': forms.TextInput(
                attrs={'class': 'bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500 w-full', 'placeholder': '快递单号等辅助信息（可选）'}
            ),
            'remark': forms.Textarea(
                attrs={'rows': 3, 'class': 'bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500 w-full', 'placeholder': '调拨备注'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        whs = Warehouse.objects.filter(is_active=True).order_by('code')
        self.fields['from_warehouse'].queryset = whs
        self.fields['to_warehouse'].queryset = whs

    def clean(self):
        cleaned_data = super().clean()
        from_wh = cleaned_data.get('from_warehouse')
        to_wh = cleaned_data.get('to_warehouse')
        quantity = cleaned_data.get('quantity')
        material = cleaned_data.get('material')

        if from_wh and to_wh and from_wh.pk == to_wh.pk:
            self.add_error('to_warehouse', '来源仓库和目标仓库不能相同')

        if from_wh and material and quantity:
            from_stock = WarehouseStock.objects.filter(
                warehouse=from_wh, material=material
            ).first()
            available = from_stock.quantity if from_stock else 0
            if available < quantity:
                self.add_error('quantity', f'来源仓库库存不足，当前可用: {available}')

        return cleaned_data
