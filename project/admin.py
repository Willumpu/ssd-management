from django.contrib import admin
from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['project_number', 'name', 'customer', 'status', 'created_by', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['project_number', 'name', 'description']
    readonly_fields = ['project_number', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
