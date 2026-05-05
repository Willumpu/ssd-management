"""
研发需求管理 URL 配置
"""
from django.urls import path
from . import views

app_name = 'rd_requirement'

urlpatterns = [
    path('', views.RDRequirementListView.as_view(), name='requirement_list'),
    path('create/', views.RDRequirementCreateView.as_view(), name='requirement_create'),
    path('<int:pk>/', views.RDRequirementDetailView.as_view(), name='requirement_detail'),
    path('<int:pk>/update/', views.RDRequirementUpdateView.as_view(), name='requirement_update'),
    path('<int:pk>/add-progress/', views.RequirementProgressCreateView.as_view(), name='add_progress'),
    path('<int:pk>/add-attachment/', views.RequirementAttachmentCreateView.as_view(), name='add_attachment'),
    path('<int:pk>/add-comment/', views.RequirementCommentCreateView.as_view(), name='add_comment'),
    path('<int:pk>/delete-comment/<int:comment_pk>/', views.RequirementCommentDeleteView.as_view(), name='delete_comment'),
]
