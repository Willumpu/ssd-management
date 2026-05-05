"""
FAE 任务管理 URL 配置
"""
from django.urls import path
from . import views

app_name = 'fae'

urlpatterns = [
    path('tasks/', views.FAETaskListView.as_view(), name='task_list'),
    path('tasks/create/', views.FAETaskCreateView.as_view(), name='task_create'),
    path('tasks/<int:pk>/', views.FAETaskDetailView.as_view(), name='task_detail'),
    path('tasks/<int:pk>/update/', views.FAETaskUpdateView.as_view(), name='task_update'),
    path('tasks/<int:pk>/delete/', views.FAETaskDeleteView.as_view(), name='task_delete'),
    path('tasks/<int:pk>/review/', views.FAETaskReviewView.as_view(), name='task_review'),
    path('tasks/<int:pk>/change-status/', views.FAETaskChangeStatusView.as_view(), name='task_change_status'),
    path('tasks/<int:pk>/add-comment/', views.FAETaskCommentCreateView.as_view(), name='add_comment'),
    path('tasks/comments/<int:pk>/delete/', views.FAETaskCommentDeleteView.as_view(), name='delete_comment'),
    path('customers/', views.CustomerListView.as_view(), name='customer_list'),
    path('customers/create/', views.CustomerCreateView.as_view(), name='customer_create'),
    path('notifications/<int:pk>/mark-read/', views.NotificationMarkReadView.as_view(), name='notification_mark_read'),
    path('notifications/task/<int:pk>/mark-read/', views.NotificationMarkTaskReadView.as_view(), name='notification_mark_task_read'),
    path('user/settings/', views.UserSettingsView.as_view(), name='user_settings'),
]
