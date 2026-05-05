"""
样品物料库存管理视图
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View, ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.db import models, transaction
from .models import SampleMaterial, MaterialTransfer, Warehouse, WarehouseStock
from .forms import SampleMaterialForm, MaterialTransferForm
from fae.models import User, Customer


# ==================== 库存总览 ====================

class InventoryOverviewView(LoginRequiredMixin, View):
    """库存总览 - 按仓库分组展示"""
    template_name = 'sample_shipment/inventory_overview.html'

    def get(self, request):
        # 确保3个固定仓库存在
        Warehouse.get_or_create_default_warehouses()

        # 只获取3个固定仓库
        warehouses = Warehouse.objects.filter(is_active=True).order_by('code')
        current_wh_id = request.GET.get('warehouse')

        # 当前选中的仓库
        current_warehouse = None
        stocks = []
        if current_wh_id:
            current_warehouse = get_object_or_404(Warehouse, pk=current_wh_id)
            stocks = WarehouseStock.objects.filter(
                warehouse=current_warehouse, quantity__gt=0
            ).select_related('material').order_by('-quantity')

        # 统计各仓库物料种数和总数量
        warehouse_stats = []
        for wh in warehouses:
            wh_stocks = WarehouseStock.objects.filter(warehouse=wh, quantity__gt=0)
            total_qty = sum(s.quantity for s in wh_stocks)
            warehouse_stats.append({
                'warehouse': wh,
                'material_count': wh_stocks.count(),
                'total_qty': total_qty,
            })

        context = {
            'warehouse_stats': warehouse_stats,
            'current_warehouse': current_warehouse,
            'stocks': stocks,
        }
        return render(request, self.template_name, context)


# ==================== 物料档案 ====================

class SampleMaterialListView(LoginRequiredMixin, ListView):
    """物料档案列表"""
    model = SampleMaterial
    template_name = 'sample_shipment/material_list.html'
    context_object_name = 'materials'
    paginate_by = 20

    def get_queryset(self):
        queryset = SampleMaterial.objects.select_related('related_customer')
        category = self.request.GET.get('category')
        status = self.request.GET.get('status')
        search = self.request.GET.get('search')

        if category:
            queryset = queryset.filter(category=category)
        if status:
            queryset = queryset.filter(status=status)
        if search:
            queryset = queryset.filter(
                models.Q(material_number__icontains=search) |
                models.Q(name__icontains=search) |
                models.Q(description__icontains=search) |
                models.Q(related_customer__customer_code__icontains=search)
            )
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category_choices'] = SampleMaterial.CATEGORY_CHOICES
        context['status_choices'] = SampleMaterial.STATUS_CHOICES
        context['current_category'] = self.request.GET.get('category', '')
        context['current_status'] = self.request.GET.get('status', '')
        context['search_query'] = self.request.GET.get('search', '')
        return context


class SampleMaterialDetailView(LoginRequiredMixin, DetailView):
    """物料详情"""
    model = SampleMaterial
    template_name = 'sample_shipment/material_detail.html'
    context_object_name = 'material'

    def get_queryset(self):
        return super().get_queryset().select_related('related_customer')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stocks'] = self.object.stocks.select_related('warehouse').filter(quantity__gt=0)
        context['total_stock'] = self.object.get_total_stock()
        context['transfers'] = self.object.transfers.select_related('from_warehouse', 'to_warehouse', 'operator').all()[:30]
        return context


class SampleMaterialCreateView(LoginRequiredMixin, CreateView):
    """创建物料档案"""
    model = SampleMaterial
    form_class = SampleMaterialForm
    template_name = 'sample_shipment/material_form.html'

    def get_form(self, form_class=None):
        # 确保3个固定仓库存在并作为默认选项（必须在 super().get_form() 之前）
        Warehouse.get_or_create_default_warehouses()
        form = super().get_form(form_class)
        form.fields['related_customer'].queryset = Customer.objects.all().order_by('customer_code')
        
        # 如果从项目跳转过来，自动填充项目
        project_id = self.request.GET.get('project')
        if project_id:
            from project.models import Project
            form.fields['project'].queryset = Project.objects.filter(pk=project_id)
            form.initial['project'] = int(project_id)
            # project 字段在模板中根据 request.GET.project 条件隐藏/显示
        
        return form

    def form_valid(self, form):
        with transaction.atomic():
            # 先保存物料
            response = super().form_valid(form)

            # 创建初始库存
            initial_warehouse = form.cleaned_data['initial_warehouse']
            initial_quantity = form.cleaned_data['initial_quantity']

            if initial_quantity > 0:
                WarehouseStock.objects.create(
                    warehouse=initial_warehouse,
                    material=self.object,
                    quantity=initial_quantity
                )

        messages.success(self.request, f'物料档案 {self.object.material_number} 创建成功，初始库存 {initial_quantity} 已放入 {initial_warehouse.name}')
        return response

    def get_success_url(self):
        return reverse_lazy('sample_shipment:material_detail', kwargs={'pk': self.object.pk})


class SampleMaterialUpdateView(LoginRequiredMixin, UpdateView):
    """编辑物料档案"""
    model = SampleMaterial
    form_class = SampleMaterialForm
    template_name = 'sample_shipment/material_form.html'

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['related_customer'].queryset = Customer.objects.all().order_by('customer_code')
        # 编辑时不显示初始仓库和初始数量（已通过调拨管理）
        form.fields.pop('initial_warehouse')
        form.fields.pop('initial_quantity')
        return form

    def form_valid(self, form):
        messages.success(self.request, f'物料档案 {self.object.material_number} 更新成功')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('sample_shipment:material_detail', kwargs={'pk': self.object.pk})


class SampleMaterialDeleteView(LoginRequiredMixin, DeleteView):
    """删除物料档案"""
    model = SampleMaterial
    template_name = 'sample_shipment/material_confirm_delete.html'
    success_url = reverse_lazy('sample_shipment:material_list')

    def delete(self, request, *args, **kwargs):
        material = self.get_object()
        messages.success(request, f'物料档案 {material.material_number} 已删除')
        return super().delete(request, *args, **kwargs)


# ==================== 调拨/流转 ====================

class MaterialTransferListView(LoginRequiredMixin, ListView):
    """流转记录列表"""
    model = MaterialTransfer
    template_name = 'sample_shipment/transfer_list.html'
    context_object_name = 'transfers'
    paginate_by = 20

    def get_queryset(self):
        queryset = MaterialTransfer.objects.select_related('material', 'from_warehouse', 'to_warehouse', 'operator')
        warehouse = self.request.GET.get('warehouse')
        search = self.request.GET.get('search')

        if warehouse:
            queryset = queryset.filter(
                models.Q(from_warehouse=warehouse) | models.Q(to_warehouse=warehouse)
            )
        if search:
            queryset = queryset.filter(
                models.Q(transfer_number__icontains=search) |
                models.Q(material__name__icontains=search) |
                models.Q(material__material_number__icontains=search) |
                models.Q(tracking_info__icontains=search)
            )
        return queryset.order_by('-transfer_date', '-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['warehouses'] = Warehouse.objects.filter(is_active=True).order_by('code')
        context['current_warehouse'] = self.request.GET.get('warehouse', '')
        context['search_query'] = self.request.GET.get('search', '')
        return context


class MaterialTransferCreateView(LoginRequiredMixin, CreateView):
    """创建调拨/流转记录"""
    model = MaterialTransfer
    form_class = MaterialTransferForm
    template_name = 'sample_shipment/transfer_form.html'

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        material_id = self.request.GET.get('material')
        if material_id:
            # 从详情页带过来的物料，限制下拉框只有该物料并默认选中
            form.fields['material'].queryset = SampleMaterial.objects.filter(pk=material_id)
            form.initial['material'] = int(material_id)
            # 自动填写来源仓库：选该物料库存最多的仓库
            stock = WarehouseStock.objects.filter(
                material_id=material_id, quantity__gt=0
            ).order_by('-quantity').select_related('warehouse').first()
            if stock:
                form.initial['from_warehouse'] = stock.warehouse.pk
        else:
            form.fields['material'].queryset = SampleMaterial.objects.all().order_by('-created_at')
        return form

    def form_valid(self, form):
        with transaction.atomic():
            form.instance.operator = self.request.user
            response = super().form_valid(form)

            # 自动更新仓库库存
            from_wh = self.object.from_warehouse
            to_wh = self.object.to_warehouse
            material = self.object.material
            qty = self.object.quantity

            # 减少来源仓库库存
            from_stock, _ = WarehouseStock.objects.get_or_create(
                warehouse=from_wh, material=material, defaults={'quantity': 0}
            )
            from_stock.quantity -= qty
            from_stock.save()

            # 增加目标仓库库存
            to_stock, _ = WarehouseStock.objects.get_or_create(
                warehouse=to_wh, material=material, defaults={'quantity': 0}
            )
            to_stock.quantity += qty
            to_stock.save()

        # 记录项目时间线（如果物料归属到项目）
        if material.project:
            from project.signals import record_project_activity
            desc = f"物料：{material.name} | 来源：{from_wh.name} | 目标：{to_wh.name} | 数量：{qty}"
            if self.object.tracking_info:
                desc += f" | 物流：{self.object.tracking_info}"
            record_project_activity(
                project=material.project,
                actor=self.request.user,
                action='transfer',
                instance=self.object,
                description=desc
            )

        messages.success(
            self.request,
            f'调拨成功：{material.name} {from_wh.name} → {to_wh.name} × {qty}'
        )
        return response

    def get_success_url(self):
        return reverse_lazy('sample_shipment:transfer_list')
