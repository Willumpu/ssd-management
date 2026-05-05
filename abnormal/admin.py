"""
异常样品管理 Admin 配置
"""
from django.contrib import admin
from .models import AbnormalSample, TestRecordEntry, AbnormalLogFile, AbnormalComment, AbnormalLog


class TestRecordEntryInline(admin.TabularInline):
    model = TestRecordEntry
    extra = 0


class AbnormalLogFileInline(admin.TabularInline):
    model = AbnormalLogFile
    extra = 0


class AbnormalCommentInline(admin.TabularInline):
    model = AbnormalComment
    extra = 0
    readonly_fields = ['created_at']


class AbnormalLogInline(admin.TabularInline):
    model = AbnormalLog
    extra = 0
    readonly_fields = ['operator', 'action', 'old_status', 'new_status', 'created_at']
    can_delete = False


@admin.register(AbnormalSample)
class AbnormalSampleAdmin(admin.ModelAdmin):
    list_display = ['sample_number', 'customer', 'status', 'priority', 'assignee', 'created_at']
    list_filter = ['status', 'priority', 'created_at']
    search_fields = ['sample_number', 'customer__customer_code', 'abnormal_description']
    inlines = [TestRecordEntryInline, AbnormalLogFileInline, AbnormalCommentInline, AbnormalLogInline]
    date_hierarchy = 'created_at'


@admin.register(TestRecordEntry)
class TestRecordEntryAdmin(admin.ModelAdmin):
    list_display = ['abnormal_sample', 'record_time', 'operator']
    list_filter = ['record_time']


@admin.register(AbnormalLogFile)
class AbnormalLogFileAdmin(admin.ModelAdmin):
    list_display = ['abnormal_sample', 'log_type', 'uploaded_by', 'uploaded_at']
    list_filter = ['log_type', 'uploaded_at']


@admin.register(AbnormalComment)
class AbnormalCommentAdmin(admin.ModelAdmin):
    list_display = ['abnormal_sample', 'author', 'created_at']
    list_filter = ['created_at']
    search_fields = ['content', 'abnormal_sample__sample_number', 'author__username']


@admin.register(AbnormalLog)
class AbnormalLogAdmin(admin.ModelAdmin):
    list_display = ['abnormal_sample', 'action', 'operator', 'created_at']
    list_filter = ['created_at', 'old_status', 'new_status']
    search_fields = ['abnormal_sample__sample_number', 'action', 'operator__username']
