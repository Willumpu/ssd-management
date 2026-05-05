"""
样品物料库存管理后台
"""
from django.contrib import admin
from .models import Warehouse, SampleMaterial, WarehouseStock, MaterialTransfer


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'warehouse_type', 'related_customer', 'is_active']
    list_filter = ['warehouse_type', 'is_active']
    search_fields = ['code', 'name']


@admin.register(SampleMaterial)
class SampleMaterialAdmin(admin.ModelAdmin):
    list_display = ['material_number', 'name', 'category', 'status', 'related_customer', 'created_at']
    list_filter = ['category', 'status', 'created_at']
    search_fields = ['material_number', 'name', 'description']
    readonly_fields = ['material_number', 'created_at', 'updated_at']


@admin.register(WarehouseStock)
class WarehouseStockAdmin(admin.ModelAdmin):
    list_display = ['warehouse', 'material', 'quantity', 'updated_at']
    list_filter = ['warehouse']
    search_fields = ['material__name', 'material__material_number']
    readonly_fields = ['updated_at']


@admin.register(MaterialTransfer)
class MaterialTransferAdmin(admin.ModelAdmin):
    list_display = ['transfer_number', 'material', 'from_warehouse', 'to_warehouse', 'quantity', 'transfer_date', 'operator']
    list_filter = ['from_warehouse', 'to_warehouse', 'transfer_date']
    search_fields = ['transfer_number', 'material__name', 'material__material_number', 'tracking_info']
    readonly_fields = ['transfer_number', 'created_at']
    date_hierarchy = 'transfer_date'
