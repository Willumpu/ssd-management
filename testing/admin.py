"""
测试跟踪管理 Admin 配置
"""
from django.contrib import admin
from .models import (
    TestItem, TestContent, TestAbnormalRelation, TestComment, TestItemLog,
    TestParameterDefinition, TestItemParameter, AbnormalReason, TestItemAbnormalAnalysis
)


class TestAbnormalRelationInline(admin.TabularInline):
    model = TestAbnormalRelation
    extra = 0
    raw_id_fields = ['abnormal_sample']


class TestItemLogInline(admin.TabularInline):
    model = TestItemLog
    extra = 0
    readonly_fields = ['operator', 'action', 'old_status', 'new_status', 'created_at']
    can_delete = False


class TestItemParameterInline(admin.TabularInline):
    model = TestItemParameter
    extra = 0
    autocomplete_fields = ['parameter']


class TestItemAbnormalAnalysisInline(admin.TabularInline):
    model = TestItemAbnormalAnalysis
    extra = 0
    autocomplete_fields = ['reason']
    readonly_fields = ['created_by', 'created_at']


@admin.register(TestContent)
class TestContentAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active', 'order', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'code']
    list_editable = ['is_active', 'order']
    ordering = ['order', 'id']


@admin.register(TestItem)
class TestItemAdmin(admin.ModelAdmin):
    list_display = ['test_number', 'tracker', 'customer', 'test_content', 'status', 
                    'total_samples', 'passed_samples', 'abnormal_samples_count', 
                    'testing_samples', 'retesting_samples', 'created_at']
    list_filter = ['test_content', 'status', 'created_at']
    search_fields = ['test_number', 'customer__customer_code', 'test_content__name']
    list_editable = ['test_content']
    autocomplete_fields = ['test_content']
    inlines = [TestAbnormalRelationInline, TestItemLogInline, TestItemParameterInline, TestItemAbnormalAnalysisInline]
    date_hierarchy = 'created_at'


@admin.register(TestParameterDefinition)
class TestParameterDefinitionAdmin(admin.ModelAdmin):
    list_display = ['name', 'param_key', 'unit', 'data_type', 'default_value', 'is_active', 'order']
    list_filter = ['data_type', 'is_active']
    search_fields = ['name', 'param_key']
    list_editable = ['default_value', 'order', 'is_active']
    ordering = ['order', 'id']


@admin.register(AbnormalReason)
class AbnormalReasonAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'is_active', 'order', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    list_editable = ['is_active', 'order']
    ordering = ['order', 'id']


@admin.register(TestItemAbnormalAnalysis)
class TestItemAbnormalAnalysisAdmin(admin.ModelAdmin):
    list_display = ['test_item', 'reason', 'quantity', 'created_by', 'created_at']
    list_filter = ['reason', 'created_at']
    search_fields = ['test_item__test_number', 'reason__name', 'description']
    autocomplete_fields = ['test_item', 'reason']
    readonly_fields = ['created_by', 'created_at', 'updated_at']


@admin.register(TestComment)
class TestCommentAdmin(admin.ModelAdmin):
    list_display = ['test', 'author', 'content', 'created_at']
    list_filter = ['created_at']
    search_fields = ['test__test_number', 'content', 'author__username']
