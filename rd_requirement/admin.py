"""
研发需求管理 Admin 配置
"""
from django.contrib import admin
from .models import RDRequirement, RequirementProgress, RequirementAttachment, RequirementComment, RequirementLog


class RequirementProgressInline(admin.TabularInline):
    model = RequirementProgress
    extra = 0


class RequirementAttachmentInline(admin.TabularInline):
    model = RequirementAttachment
    extra = 0


class RequirementLogInline(admin.TabularInline):
    model = RequirementLog
    extra = 0
    readonly_fields = ['created_at', 'operator', 'action', 'old_status', 'new_status', 'comment']


@admin.register(RDRequirement)
class RDRequirementAdmin(admin.ModelAdmin):
    list_display = ['requirement_number', 'title', 'requirement_type', 'priority', 
                    'status', 'assignee', 'report_date']
    list_filter = ['requirement_type', 'priority', 'status', 'created_at']
    search_fields = ['requirement_number', 'title', 'description']
    inlines = [RequirementProgressInline, RequirementAttachmentInline, RequirementLogInline]
    date_hierarchy = 'created_at'

@admin.register(RequirementProgress)
class RequirementProgressAdmin(admin.ModelAdmin):
    list_display = ['requirement', 'progress_date', 'progress_percent', 'reported_by']
    list_filter = ['progress_date']


@admin.register(RequirementComment)
class RequirementCommentAdmin(admin.ModelAdmin):
    list_display = ['requirement', 'author', 'content', 'created_at']
    list_filter = ['created_at']
    search_fields = ['content', 'requirement__requirement_number']


@admin.register(RequirementLog)
class RequirementLogAdmin(admin.ModelAdmin):
    list_display = ['requirement', 'operator', 'action', 'old_status', 'new_status', 'created_at']
    list_filter = ['created_at', 'action']
    search_fields = ['requirement__requirement_number', 'action', 'comment']
    readonly_fields = ['created_at']
