"""
项目管理视图
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.db import models
from .models import Project, ProductionPlan
from .forms import ProjectForm, ProductionPlanForm


class ProjectListView(LoginRequiredMixin, ListView):
    """项目列表"""
    model = Project
    template_name = 'project/project_list.html'
    context_object_name = 'projects'
    paginate_by = 20

    def get_queryset(self):
        queryset = Project.objects.select_related('customer', 'created_by')
        status = self.request.GET.get('status')
        search = self.request.GET.get('search')
        if status:
            queryset = queryset.filter(status=status)
        if search:
            queryset = queryset.filter(
                models.Q(project_number__icontains=search) |
                models.Q(name__icontains=search) |
                models.Q(description__icontains=search)
            )
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Project.STATUS_CHOICES
        context['current_status'] = self.request.GET.get('status', '')
        context['search_query'] = self.request.GET.get('search', '')
        return context


class ProjectDetailView(LoginRequiredMixin, DetailView):
    """项目详情 - 展示关联的所有模块内容"""
    model = Project
    template_name = 'project/project_detail.html'
    context_object_name = 'project'

    def get_queryset(self):
        return super().get_queryset().select_related('customer', 'created_by')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object

        # 各模块关联数据
        context['fae_tasks'] = project.fae_tasks.select_related('customer', 'assignee').all()[:50]
        context['test_items'] = project.test_items.select_related('customer', 'tracker').prefetch_related('fae_tasks').all()[:50]
        for test in context['test_items']:
            if test.status == 'completed' and test.total_samples > 0:
                test.yield_rate = round(test.passed_samples / test.total_samples * 100, 1)
            else:
                test.yield_rate = None
        context['abnormal_samples'] = project.abnormal_samples.select_related('customer', 'assignee').all()[:50]
        context['solutions'] = project.solutions.select_related('created_by').all()[:50]
        context['rd_requirements'] = project.rd_requirements.select_related('assignee').all()[:50]
        context['sample_materials'] = project.sample_materials.select_related('related_customer').all()[:50]
        context['issues'] = project.issues.select_related('submitter', 'solution').all()[:50]
        context['production_plans'] = project.production_plans.all()
        context['production_plan_form'] = ProductionPlanForm()

        # 关联数量统计
        context['related_counts'] = project.get_related_counts()
        context['total_items'] = project.get_total_items()

        # 各模块创建URL（带project参数）
        context['create_urls'] = {
            'fae_task': f"/fae/tasks/create/?project={project.pk}",
            'test_item': f"/testing/create/?project={project.pk}",
            'abnormal_sample': f"/abnormal/create/?project={project.pk}",
            'solution': f"/solution/create/?project={project.pk}",
            'rd_requirement': f"/rd/create/?project={project.pk}",
            'sample_material': f"/shipment/materials/create/?project={project.pk}",
            'issue': f"/issue/create/?project={project.pk}",
        }

        return context


class ProjectCreateView(LoginRequiredMixin, CreateView):
    """创建项目"""
    model = Project
    form_class = ProjectForm
    template_name = 'project/project_form.html'

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, f'项目 {form.instance.project_number} 创建成功')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('project:project_detail', kwargs={'pk': self.object.pk})


class ProjectUpdateView(LoginRequiredMixin, UpdateView):
    """编辑项目"""
    model = Project
    form_class = ProjectForm
    template_name = 'project/project_form.html'

    def form_valid(self, form):
        messages.success(self.request, f'项目 {self.object.project_number} 更新成功')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('project:project_detail', kwargs={'pk': self.object.pk})


class ProjectDeleteView(LoginRequiredMixin, DeleteView):
    """删除项目"""
    model = Project
    template_name = 'project/project_confirm_delete.html'
    success_url = reverse_lazy('project:project_list')

    def delete(self, request, *args, **kwargs):
        project = self.get_object()
        messages.success(request, f'项目 {project.project_number} 已删除')
        return super().delete(request, *args, **kwargs)


class ProductionPlanCreateView(LoginRequiredMixin, View):
    """为项目添加生产方案"""
    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        form = ProductionPlanForm(request.POST)
        if form.is_valid():
            plan = form.save(commit=False)
            plan.project = project
            plan.save()
            messages.success(request, f'生产方案 {plan.name} 添加成功')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
        return redirect('project:project_detail', pk=pk)


class ProductionPlanUpdateView(LoginRequiredMixin, UpdateView):
    """编辑生产方案"""
    model = ProductionPlan
    form_class = ProductionPlanForm
    template_name = 'project/productionplan_form.html'
    pk_url_kwarg = 'plan_pk'

    def get_object(self, queryset=None):
        project = get_object_or_404(Project, pk=self.kwargs['pk'])
        return get_object_or_404(ProductionPlan, pk=self.kwargs['plan_pk'], project=project)

    def get_success_url(self):
        return reverse_lazy('project:project_detail', kwargs={'pk': self.kwargs['pk']})

    def form_valid(self, form):
        messages.success(self.request, f'生产方案 {self.object.name} 更新成功')
        return super().form_valid(form)


class ProductionPlanDeleteView(LoginRequiredMixin, View):
    """删除生产方案"""
    def post(self, request, pk, plan_pk):
        project = get_object_or_404(Project, pk=pk)
        plan = get_object_or_404(ProductionPlan, pk=plan_pk, project=project)
        plan.delete()
        messages.success(request, '生产方案已删除')
        return redirect('project:project_detail', pk=pk)
