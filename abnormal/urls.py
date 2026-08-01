"""
异常样品管理 URL 配置
"""
from django.urls import path
from . import views

app_name = 'abnormal'

urlpatterns = [
    path('', views.AbnormalSampleListView.as_view(), name='abnormal_list'),
    path('create/', views.AbnormalSampleCreateView.as_view(), name='abnormal_create'),
    path('batch-create/', views.AbnormalSampleBatchCreateView.as_view(), name='abnormal_batch_create'),
    path('batch-upload-log/', views.AbnormalBatchUploadLogView.as_view(), name='abnormal_batch_upload_log'),
    path('<int:pk>/', views.AbnormalSampleDetailView.as_view(), name='abnormal_detail'),
    path('<int:pk>/update/', views.AbnormalSampleUpdateView.as_view(), name='abnormal_update'),
    path('<int:pk>/change-status/', views.AbnormalSampleChangeStatusView.as_view(), name='change_status'),
    path('<int:pk>/add-record/', views.TestRecordEntryCreateView.as_view(), name='add_record'),
    path('<int:pk>/upload-log/', views.AbnormalLogFileCreateView.as_view(), name='upload_log'),
    path('log-files/<int:pk>/view/', views.AbnormalLogFileView.as_view(), name='log_file_view'),
    path('log-files/<int:pk>/delete/', views.AbnormalLogFileDeleteView.as_view(), name='log_file_delete'),
    path('<int:pk>/add-comment/', views.AbnormalCommentCreateView.as_view(), name='add_comment'),
    path('comments/<int:pk>/delete/', views.AbnormalCommentDeleteView.as_view(), name='delete_comment'),
    # API
    path('api/list/', views.AbnormalSampleAPIListView.as_view(), name='api_list'),
]
