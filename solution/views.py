"""
方案管理视图
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.db import models
from .models import Solution, ControllerModel, FlashModel, PCBModel, SolutionComment, SolutionLog
from .forms import SolutionCommentForm, SolutionForm


class SolutionListView(LoginRequiredMixin, ListView):
    """方案列表"""
    model = Solution
    template_name = 'solution/solution_list.html'
    context_object_name = 'solutions'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        controller = self.request.GET.get('controller')
        flash = self.request.GET.get('flash')
        status = self.request.GET.get('status')
        search = self.request.GET.get('search')
        
        if controller:
            queryset = queryset.filter(controller_model_id=controller)
        if flash:
            queryset = queryset.filter(flash_model_id=flash)
        if status:
            queryset = queryset.filter(status=status)
        if search:
            queryset = queryset.filter(
                models.Q(solution_number__icontains=search) |
                models.Q(controller_model__name__icontains=search) |
                models.Q(flash_model__name__icontains=search) |
                models.Q(software_version__icontains=search)
            )
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 获取所有启用的型号
        context['controller_models'] = ControllerModel.objects.filter(is_active=True).order_by('name')
        context['flash_models'] = FlashModel.objects.filter(is_active=True).order_by('name')
        context['status_choices'] = Solution.STATUS_CHOICES
        return context


class SolutionDetailView(LoginRequiredMixin, DetailView):
    """方案详情"""
    model = Solution
    template_name = 'solution/solution_detail.html'
    context_object_name = 'solution'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comments'] = self.object.comments.select_related('author').all()
        context['comment_form'] = SolutionCommentForm()
        return context


class SolutionCreateView(LoginRequiredMixin, CreateView):
    """创建方案"""
    model = Solution
    template_name = 'solution/solution_form.html'
    form_class = SolutionForm
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['controller_model'].queryset = ControllerModel.objects.filter(is_active=True).order_by('name')
        form.fields['flash_model'].queryset = FlashModel.objects.filter(is_active=True).order_by('name')
        form.fields['pcb_models'].queryset = PCBModel.objects.filter(is_active=True).order_by('name')
        form.fields['pcb_models'].widget.attrs.update({'class': 'space-y-2'})
        
        # 如果从项目跳转过来，自动填充项目
        project_id = self.request.GET.get('project')
        if project_id:
            from project.models import Project
            form.fields['project'].queryset = Project.objects.filter(pk=project_id)
            form.initial['project'] = int(project_id)
            # project 字段在模板中根据 request.GET.project 条件隐藏/显示
        
        return form
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        # 获取状态显示名称
        status_dict = dict(Solution.STATUS_CHOICES)
        status_display = status_dict.get(self.object.status, self.object.status)
        # 创建操作日志
        SolutionLog.objects.create(
            solution=self.object,
            operator=self.request.user,
            action=f'创建方案，初始状态：{status_display}',
            new_status=self.object.status,
            comment='创建新方案'
        )
        messages.success(self.request, '方案创建成功')
        return response
    
    def get_success_url(self):
        return reverse_lazy('solution:solution_detail', kwargs={'pk': self.object.pk})


class SolutionUpdateView(LoginRequiredMixin, UpdateView):
    """更新方案"""
    model = Solution
    template_name = 'solution/solution_form.html'
    form_class = SolutionForm
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['controller_model'].queryset = ControllerModel.objects.filter(is_active=True).order_by('name')
        form.fields['flash_model'].queryset = FlashModel.objects.filter(is_active=True).order_by('name')
        form.fields['pcb_models'].queryset = PCBModel.objects.filter(is_active=True).order_by('name')
        form.fields['pcb_models'].widget.attrs.update({'class': 'space-y-2'})
        return form
    
    def form_valid(self, form):
        # 获取原状态
        old_status = self.object.status
        # 获取表单中的新状态
        new_status_from_form = form.cleaned_data.get('status')
        
        # 获取原值用于比较
        old_controller = self.object.controller_model
        old_flash = self.object.flash_model
        old_flash_count = self.object.flash_count
        old_software_version = self.object.software_version
        old_pcb_models = set(self.object.pcb_models.all())
        
        # 先保存表单（这会更新所有字段包括状态）
        response = super().form_valid(form)
        
        # 刷新对象获取最新数据库值
        self.object.refresh_from_db()
        
        # 获取新状态
        new_status = self.object.status
        # 获取状态显示名称
        status_dict = dict(Solution.STATUS_CHOICES)
        old_status_display = status_dict.get(old_status, old_status)
        new_status_display = status_dict.get(new_status, new_status)
        # 收集变更字段和详情
        changed_fields = []
        detail_changes = []
        if old_status != new_status:
            changed_fields.append('状态')
            detail_changes.append(f"状态：{old_status_display} → {new_status_display}")
        if old_controller != self.object.controller_model:
            changed_fields.append('主控型号')
            detail_changes.append(f"主控型号：{old_controller} → {self.object.controller_model}")
        if old_flash != self.object.flash_model:
            changed_fields.append('Flash型号')
            detail_changes.append(f"Flash型号：{old_flash} → {self.object.flash_model}")
        if old_flash_count != self.object.flash_count:
            changed_fields.append('Flash数量')
            detail_changes.append(f"Flash数量：{old_flash_count} → {self.object.flash_count}")
        if old_software_version != self.object.software_version:
            changed_fields.append('软件版本')
            detail_changes.append(f"软件版本：{old_software_version} → {self.object.software_version}")
        new_pcb_models = set(self.object.pcb_models.all())
        if old_pcb_models != new_pcb_models:
            changed_fields.append('PCB型号')
            old_names = ', '.join([str(p) for p in old_pcb_models]) or '无'
            new_names = ', '.join([str(p) for p in new_pcb_models]) or '无'
            detail_changes.append(f"PCB型号：{old_names} → {new_names}")
        # 构建action
        if changed_fields:
            action = f"更新方案（{', '.join(changed_fields)}）"
            comment = '；'.join(detail_changes)
        else:
            action = '更新方案'
            comment = '更新方案信息'
        # 创建操作日志
        SolutionLog.objects.create(
            solution=self.object,
            operator=self.request.user,
            action=action,
            old_status=old_status,
            new_status=new_status,
            comment=comment
        )
        
        # 记录项目时间线（仅状态变更时）
        if self.object.project and old_status != new_status:
            from project.signals import record_project_activity
            status_dict = dict(Solution.STATUS_CHOICES)
            old_status_display = status_dict.get(old_status, old_status)
            new_status_display = status_dict.get(new_status, new_status)
            record_project_activity(
                project=self.object.project,
                actor=self.request.user,
                action='status_change',
                instance=self.object,
                description=f"状态：{old_status_display} → {new_status_display}"
            )
        
        messages.success(self.request, '方案更新成功')
        return response
    
    def form_invalid(self, form):
        # 显示表单验证错误
        for field, errors in form.errors.items():
            for error in errors:
                field_name = form.fields[field].label if field in form.fields else field
                messages.error(self.request, f'{field_name}: {error}')
        return super().form_invalid(form)
    
    def get_success_url(self):
        return reverse_lazy('solution:solution_detail', kwargs={'pk': self.object.pk})


class SolutionDeleteView(LoginRequiredMixin, DeleteView):
    """删除方案"""
    model = Solution
    template_name = 'solution/solution_confirm_delete.html'
    success_url = reverse_lazy('solution:solution_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, '方案删除成功')
        return super().delete(request, *args, **kwargs)


class SolutionCommentCreateView(LoginRequiredMixin, CreateView):
    """添加方案评论"""
    model = SolutionComment
    form_class = SolutionCommentForm
    
    def form_valid(self, form):
        solution = get_object_or_404(Solution, pk=self.kwargs['pk'])
        form.instance.solution = solution
        form.instance.author = self.request.user
        messages.success(self.request, '评论添加成功')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('solution:solution_detail', kwargs={'pk': self.kwargs['pk']})


class SolutionCommentDeleteView(LoginRequiredMixin, View):
    """删除方案评论（仅评论作者可删除）"""
    def post(self, request, pk):
        comment = get_object_or_404(SolutionComment, pk=pk)
        solution_pk = comment.solution.pk
        
        # 验证是否为评论作者
        if comment.author != request.user:
            messages.error(request, '您只能删除自己发布的评论')
            return redirect('solution:solution_detail', pk=solution_pk)
        
        comment.delete()
        messages.success(request, '评论已删除')
        return redirect('solution:solution_detail', pk=solution_pk)
