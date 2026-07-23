from django.contrib import admin
from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['project_number', 'name', 'customer', 'phase', 'status', 'sample_total_quantity', 'current_yield', 'yield_type', 'created_by', 'created_at']
    list_filter = ['phase', 'status', 'yield_type', 'created_at']
    search_fields = ['project_number', 'name', 'description']
    readonly_fields = ['project_number', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
