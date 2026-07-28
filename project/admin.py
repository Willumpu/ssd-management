from django.contrib import admin
from .models import Project, ProductionPlan


class ProductionPlanInline(admin.TabularInline):
    model = ProductionPlan
    extra = 0
    fields = ('name', 'yield_value', 'yield_type', 'production_quantity', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['project_number', 'name', 'customer', 'phase', 'status', 'sample_total_quantity', 'created_by', 'created_at']
    list_filter = ['phase', 'status', 'created_at']
    search_fields = ['project_number', 'name', 'description']
    readonly_fields = ['project_number', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    inlines = [ProductionPlanInline]


@admin.register(ProductionPlan)
class ProductionPlanAdmin(admin.ModelAdmin):
    list_display = ['project', 'name', 'yield_value', 'yield_type', 'production_quantity', 'created_at']
    list_filter = ['yield_type', 'created_at']
    search_fields = ['name', 'project__name', 'project__project_number']
