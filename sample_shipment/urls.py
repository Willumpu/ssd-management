"""
样品物料库存管理 URL 配置
"""
from django.urls import path
from . import views

app_name = 'sample_shipment'

urlpatterns = [
    # 库存总览
    path('', views.InventoryOverviewView.as_view(), name='inventory_overview'),

    # 物料档案
    path('materials/', views.SampleMaterialListView.as_view(), name='material_list'),
    path('materials/create/', views.SampleMaterialCreateView.as_view(), name='material_create'),
    path('materials/<int:pk>/', views.SampleMaterialDetailView.as_view(), name='material_detail'),
    path('materials/<int:pk>/update/', views.SampleMaterialUpdateView.as_view(), name='material_update'),
    path('materials/<int:pk>/delete/', views.SampleMaterialDeleteView.as_view(), name='material_delete'),

    # 调拨/流转
    path('transfers/', views.MaterialTransferListView.as_view(), name='transfer_list'),
    path('transfers/create/', views.MaterialTransferCreateView.as_view(), name='transfer_create'),
]
