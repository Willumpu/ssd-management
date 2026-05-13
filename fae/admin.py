"""
FAE 模块 Admin 配置
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Customer, FAETask, FAETaskLog, FAETaskComment, LogAnalyzerKeyword


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'role', 'department', 'is_active']
    list_filter = ['role', 'is_active', 'department']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('额外信息', {'fields': ('role', 'phone', 'department')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('额外信息', {'fields': ('role', 'phone', 'department')}),
    )


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['customer_code', 'created_at']
    list_filter = ['created_at']
    search_fields = ['customer_code']


class FAETaskLogInline(admin.TabularInline):
    model = FAETaskLog
    extra = 0
    readonly_fields = ['operator', 'action', 'old_status', 'new_status', 'created_at']
    can_delete = False


@admin.register(FAETask)
class FAETaskAdmin(admin.ModelAdmin):
    list_display = ['task_number', 'assignee', 'customer', 'task_type', 'status', 'review_result', 'created_at']
    list_filter = ['task_type', 'status', 'review_result', 'created_at']
    search_fields = ['task_number', 'customer__customer_code', 'description']
    inlines = [FAETaskLogInline]
    date_hierarchy = 'created_at'
    filter_horizontal = ['test_items']


@admin.register(FAETaskComment)
class FAETaskCommentAdmin(admin.ModelAdmin):
    list_display = ['task', 'author', 'content_preview', 'created_at']
    list_filter = ['created_at']
    search_fields = ['task__task_number', 'content', 'author__username']
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = '评论内容'


@admin.register(LogAnalyzerKeyword)
class LogAnalyzerKeywordAdmin(admin.ModelAdmin):
    list_display = ['name', 'pattern', 'regex', 'is_active', 'order', 'updated_at']
    list_filter = ['is_active', 'regex']
    search_fields = ['name', 'pattern']
    list_editable = ['is_active', 'order']
    ordering = ['order', 'id']
