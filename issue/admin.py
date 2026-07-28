from django.contrib import admin
from .models import Issue, IssueSolutionRecord, IssueSolutionDetail, IssueLog


class IssueSolutionDetailInline(admin.TabularInline):
    model = IssueSolutionDetail
    extra = 0
    fields = ('detail_type', 'content', 'test_items', 'created_by', 'created_at')
    readonly_fields = ('created_at',)


class IssueSolutionRecordInline(admin.TabularInline):
    model = IssueSolutionRecord
    extra = 0
    fields = ('created_by', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ('issue_number', 'project', 'solution', 'priority', 'status', 'submitter', 'created_at')
    list_filter = ('status', 'priority', 'created_at')
    search_fields = ('issue_number', 'project__name', 'solution__name', 'abnormal_description')
    inlines = [IssueSolutionRecordInline]


@admin.register(IssueSolutionRecord)
class IssueSolutionRecordAdmin(admin.ModelAdmin):
    list_display = ('issue', 'created_by', 'created_at')
    inlines = [IssueSolutionDetailInline]


@admin.register(IssueLog)
class IssueLogAdmin(admin.ModelAdmin):
    list_display = ('issue', 'operator', 'action', 'old_status', 'new_status', 'created_at')
    list_filter = ('created_at',)
