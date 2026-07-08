"""
测试跟踪管理 URL 配置
"""
from django.urls import path
from . import views
app_name = 'testing'

urlpatterns = [
    path('', views.TestItemListView.as_view(), name='test_list'),
    path('create/', views.TestItemCreateView.as_view(), name='test_create'),
    path('<int:pk>/', views.TestItemDetailView.as_view(), name='test_detail'),
    path('<int:pk>/update/', views.TestItemUpdateView.as_view(), name='test_update'),
    path('<int:pk>/update-count/', views.TestItemCountUpdateView.as_view(), name='test_update_count'),
    path('<int:pk>/delete/', views.TestItemDeleteView.as_view(), name='test_delete'),
    path('<int:pk>/add-comment/', views.TestCommentCreateView.as_view(), name='add_comment'),
    path('comments/<int:pk>/delete/', views.TestCommentDeleteView.as_view(), name='delete_comment'),
    # 异常原因
    path('abnormal-reasons/create/', views.AbnormalReasonCreateAPIView.as_view(), name='abnormal_reason_create'),
    # 异常样品分析
    path('<int:pk>/abnormal-analysis/add/', views.TestItemAbnormalAnalysisCreateView.as_view(), name='abnormal_analysis_add'),
    path('abnormal-analysis/<int:pk>/update/', views.TestItemAbnormalAnalysisUpdateView.as_view(), name='abnormal_analysis_update'),
    path('abnormal-analysis/<int:pk>/delete/', views.TestItemAbnormalAnalysisDeleteView.as_view(), name='abnormal_analysis_delete'),
    path('flow/fae/<int:fae_task_id>/', views.TestFlowSankeyView.as_view(), name='test_flow_sankey'),
    path('flow/fae/<int:fae_task_id>/embed/', views.SankeyEmbedView.as_view(), name='sankey_embed'),
    # 桑基图 API
    path('sankey/data/<int:fae_task_id>/', views.SankeyDataView.as_view(), name='sankey_data'),
    path('sankey/nodes/create/<int:fae_task_id>/', views.SankeyNodeCreateView.as_view(), name='sankey_node_create'),
    path('sankey/nodes/<int:node_id>/split/', views.SankeyNodeSplitView.as_view(), name='sankey_node_split'),
    path('sankey/nodes/<int:node_id>/delete/', views.SankeyNodeDeleteView.as_view(), name='sankey_node_delete'),
    path('sankey/nodes/merge/', views.SankeyNodesMergeView.as_view(), name='sankey_nodes_merge'),
    # 异常样品关联
    path('sankey/nodes/<int:node_id>/abnormal/attach/', views.SankeyNodeAbnormalAttachView.as_view(), name='sankey_node_abnormal_attach'),
    path('sankey/nodes/<int:node_id>/abnormal/detach/', views.SankeyNodeAbnormalDetachView.as_view(), name='sankey_node_abnormal_detach'),
    path('sankey/nodes/<int:node_id>/group/create/', views.SankeyNodeGroupCreateView.as_view(), name='sankey_node_group_create'),
    path('sankey/nodes/<int:node_id>/update-y/', views.SankeyNodeUpdateYView.as_view(), name='sankey_node_update_y'),
    path('sankey/abnormals/<int:fae_task_id>/', views.SankeyTaskAbnormalsView.as_view(), name='sankey_task_abnormals'),
]
