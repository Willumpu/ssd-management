"""
方案管理 Admin 配置
"""
from django.contrib import admin
from .models import ControllerModel, FlashModel, PCBModel, Solution, SolutionComment, SolutionLog


@admin.register(ControllerModel)
class ControllerModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    list_editable = ['is_active']


@admin.register(FlashModel)
class FlashModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    list_editable = ['is_active']


@admin.register(PCBModel)
class PCBModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    list_editable = ['is_active']


class SolutionLogInline(admin.TabularInline):
    """方案日志内联"""
    model = SolutionLog
    extra = 0
    readonly_fields = ['operator', 'action', 'old_status', 'new_status', 'comment', 'created_at']
    can_delete = False


@admin.register(Solution)
class SolutionAdmin(admin.ModelAdmin):
    list_display = ['solution_number', 'controller_model', 'flash_model', 'flash_count', 
                    'software_version', 'release_date', 'status']
    list_filter = ['status', 'release_date', 'controller_model', 'flash_model']
    search_fields = ['solution_number', 'controller_model__name', 'flash_model__name']
    date_hierarchy = 'release_date'
    filter_horizontal = ['pcb_models']
    inlines = [SolutionLogInline]


@admin.register(SolutionLog)
class SolutionLogAdmin(admin.ModelAdmin):
    list_display = ['solution', 'operator', 'action', 'old_status', 'new_status', 'created_at']
    list_filter = ['created_at', 'action', 'old_status', 'new_status']
    search_fields = ['solution__solution_number', 'operator__username', 'action', 'comment']
    date_hierarchy = 'created_at'
    readonly_fields = ['solution', 'operator', 'action', 'old_status', 'new_status', 'comment', 'created_at']


@admin.register(SolutionComment)
class SolutionCommentAdmin(admin.ModelAdmin):
    list_display = ['solution', 'author', 'content_preview', 'created_at']
    list_filter = ['created_at', 'solution__status']
    search_fields = ['solution__solution_number', 'author__username', 'content']
    date_hierarchy = 'created_at'
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = '评论内容'
