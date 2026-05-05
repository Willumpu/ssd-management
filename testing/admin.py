"""
测试跟踪管理 Admin 配置
"""
from django.contrib import admin
from .models import TestItem, TestAbnormalRelation, TestComment, TestItemLog


class TestAbnormalRelationInline(admin.TabularInline):
    model = TestAbnormalRelation
    extra = 0
    raw_id_fields = ['abnormal_sample']


class TestItemLogInline(admin.TabularInline):
    model = TestItemLog
    extra = 0
    readonly_fields = ['operator', 'action', 'old_status', 'new_status', 'created_at']
    can_delete = False


@admin.register(TestItem)
class TestItemAdmin(admin.ModelAdmin):
    list_display = ['test_number', 'tracker', 'customer', 'test_content', 'status', 
                    'total_samples', 'passed_samples', 'abnormal_samples_count', 'created_at']
    list_filter = ['test_content', 'status', 'created_at']
    search_fields = ['test_number', 'customer__customer_code']
    inlines = [TestAbnormalRelationInline, TestItemLogInline]
    date_hierarchy = 'created_at'


@admin.register(TestComment)
class TestCommentAdmin(admin.ModelAdmin):
    list_display = ['test', 'author', 'content', 'created_at']
    list_filter = ['created_at']
    search_fields = ['test__test_number', 'content', 'author__username']
