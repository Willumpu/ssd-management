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
    path('<int:pk>/delete/', views.TestItemDeleteView.as_view(), name='test_delete'),
    path('<int:pk>/add-comment/', views.TestCommentCreateView.as_view(), name='add_comment'),
    path('comments/<int:pk>/delete/', views.TestCommentDeleteView.as_view(), name='delete_comment'),
]
