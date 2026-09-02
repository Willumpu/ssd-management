from django.urls import path
from . import views

app_name = 'issue'

urlpatterns = [
    path('', views.IssueListView.as_view(), name='issue_list'),
    path('create/', views.IssueCreateView.as_view(), name='issue_create'),
    path('<int:pk>/', views.IssueDetailView.as_view(), name='issue_detail'),
    path('<int:pk>/update/', views.IssueUpdateView.as_view(), name='issue_update'),
    path('<int:pk>/delete/', views.IssueDeleteView.as_view(), name='issue_delete'),
    path('<int:pk>/change-status/', views.IssueChangeStatusView.as_view(), name='issue_change_status'),
    path('<int:pk>/add-solution-record/', views.IssueSolutionRecordCreateView.as_view(), name='add_solution_record'),
    path('<int:pk>/solution-record/<int:record_pk>/add-detail/', views.IssueSolutionDetailCreateView.as_view(), name='add_solution_detail'),
    path('<int:pk>/solution-record/<int:record_pk>/detail/<int:detail_pk>/update/', views.IssueSolutionDetailUpdateView.as_view(), name='edit_solution_detail'),
    path('<int:pk>/solution-record/<int:record_pk>/delete/', views.IssueSolutionRecordDeleteView.as_view(), name='delete_solution_record'),
    path('<int:pk>/abnormal-samples/create/', views.IssueAbnormalSampleCreateView.as_view(), name='create_abnormal_sample'),
    path('<int:pk>/report/', views.IssueReportView.as_view(), name='issue_report'),
]
