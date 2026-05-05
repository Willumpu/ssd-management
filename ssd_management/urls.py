"""
SSD 管理平台 URL 配置
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from fae.views import DashboardView, LoginView, LogoutView

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
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
