"""
SSD 管理平台 URL 配置
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from fae.views import (
    DashboardView, LoginView, LogoutView,
    api_test_items, api_abnormal_samples, api_log_report_submit,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', DashboardView.as_view(), name='dashboard'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('ckeditor5/', include('django_ckeditor_5.urls')),
    path('fae/', include('fae.urls')),
    path('testing/', include('testing.urls')),
    path('abnormal/', include('abnormal.urls')),
    path('solution/', include('solution.urls')),
    path('rd/', include('rd_requirement.urls')),
    path('shipment/', include('sample_shipment.urls')),
    path('project/', include('project.urls')),
    path('tools/log-analyzer/', TemplateView.as_view(template_name='tools/log_analyzer.html'), name='log_analyzer'),
    path('api/test-items/', api_test_items, name='api_test_items'),
    path('api/abnormal-samples/', api_abnormal_samples, name='api_abnormal_samples'),
    path('api/log-report/', api_log_report_submit, name='api_log_report_submit'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
