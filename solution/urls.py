"""
方案管理 URL 配置
"""
from django.urls import path
from . import views

app_name = 'solution'

urlpatterns = [
    path('', views.SolutionListView.as_view(), name='solution_list'),
    path('create/', views.SolutionCreateView.as_view(), name='solution_create'),
    path('<int:pk>/', views.SolutionDetailView.as_view(), name='solution_detail'),
    path('<int:pk>/update/', views.SolutionUpdateView.as_view(), name='solution_update'),
    path('<int:pk>/delete/', views.SolutionDeleteView.as_view(), name='solution_delete'),
    path('<int:pk>/comment/', views.SolutionCommentCreateView.as_view(), name='solution_comment_create'),
    path('comments/<int:pk>/delete/', views.SolutionCommentDeleteView.as_view(), name='delete_comment'),
]
