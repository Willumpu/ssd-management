"""
项目管理 URL 配置
"""
from django.urls import path
from . import views

app_name = 'project'

urlpatterns = [
    path('', views.ProjectListView.as_view(), name='project_list'),
    path('create/', views.ProjectCreateView.as_view(), name='project_create'),
    path('<int:pk>/', views.ProjectDetailView.as_view(), name='project_detail'),
    path('<int:pk>/update/', views.ProjectUpdateView.as_view(), name='project_update'),
    path('<int:pk>/delete/', views.ProjectDeleteView.as_view(), name='project_delete'),
    path('<int:pk>/production-plan/add/', views.ProductionPlanCreateView.as_view(), name='production_plan_add'),
    path('<int:pk>/production-plan/<int:plan_pk>/update/', views.ProductionPlanUpdateView.as_view(), name='production_plan_update'),
    path('<int:pk>/production-plan/<int:plan_pk>/delete/', views.ProductionPlanDeleteView.as_view(), name='production_plan_delete'),
]
