"""
测试跟踪管理视图
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View, ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Q
from .models import TestItem, TestAbnormalRelation, TestComment, TestItemLog
from .forms import TestCommentForm, TestItemForm, TestItemCreateForm
from fae.models import Customer, User


class TestItemListView(LoginRequiredMixin, ListView):
    """测试项列表"""
    model = TestItem
    template_name = 'testing/test_list.html'
    context_object_name = 'tests'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('customer', 'tracker', 'solution')
        
        status = self.request.GET.get('status')
        test_content = self.request.GET.get('test_content')
        search = self.request.GET.get('search')
        
        if status:
            queryset = queryset.filter(status=status)
        if test_content:
            queryset = queryset.filter(test_content=test_content)
        if search:
            queryset = queryset.filter(
                Q(test_number__icontains=search) |
                Q(customer__customer_code__icontains=search)
            )
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = TestItem.TEST_STATUS_CHOICES
        context['content_choices'] = TestItem.TEST_CONTENT_CHOICES
        return context


class TestItemDetailView(LoginRequiredMixin, DetailView):
    """测试项详情"""
    model = TestItem
    template_name = 'testing/test_detail.html'
    context_object_name = 'test'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['abnormal_relations'] = self.object.abnormal_relations.all()
        context['comments'] = self.object.comments.select_related('author').all()
        context['comment_form'] = TestCommentForm()
        return context


class TestItemCreateView(LoginRequiredMixin, CreateView):
    """创建测试项"""
    model = TestItem
    template_name = 'testing/test_form.html'
    form_class = TestItemCreateForm
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['tracker'].queryset = User.objects.filter(role__in=['fae', 'fae_leader'])
        
        # 如果从项目跳转过来，自动填充项目
        project_id = self.request.GET.get('project')
        if project_id:
            from project.models import Project
            form.fields['project'].queryset = Project.objects.filter(pk=project_id)
            form.initial['project'] = int(project_id)
            # project 字段在模板中根据 request.GET.project 条件隐藏/显示
        
        # 如果从 FAE 任务跳转过来，自动填充客户
        fae_task_id = self.request.GET.get('fae_task')
        if fae_task_id:
            from fae.models import FAETask
            try:
                fae_task = FAETask.objects.get(pk=fae_task_id)
                form.fields['customer'].initial = fae_task.customer
            except FAETask.DoesNotExist:
                pass
        
        return form
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.status = 'not_started'
        response = super().form_valid(form)
        
        # 如果从 FAE 任务跳转过来，自动关联到该任务
        fae_task_id = self.request.GET.get('fae_task') or self.request.POST.get('fae_task')
        if fae_task_id:
            from fae.models import FAETask
            try:
                fae_task = FAETask.objects.get(pk=fae_task_id)
                fae_task.test_items.add(self.object)
                # 如果 FAE 任务归属到某个项目，测试项也自动归属到同一项目
                if fae_task.project and not self.object.project:
                    self.object.project = fae_task.project
                    self.object.save(update_fields=['project'])
                messages.success(self.request, f'测试项已关联到任务 {fae_task.task_number}')
            except FAETask.DoesNotExist:
                pass
        
        # 记录项目时间线（如果从 FAE 任务跳转并继承了项目）
        if self.object.project:
            from project.signals import record_project_activity, build_create_description
            record_project_activity(
                project=self.object.project,
                actor=self.request.user,
                action='create',
                instance=self.object,
                description=build_create_description(self.object, 'test_item')
            )
        
        # 创建日志
        TestItemLog.objects.create(
            test_item=self.object,
            operator=self.request.user,
            action='创建测试项（状态：未开始）'
        )
        messages.success(self.request, '测试项创建成功')
        return response
    
    def form_invalid(self, form):
        # 显示表单验证错误
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f'{form.fields[field].label if field in form.fields else field}: {error}')
        return super().form_invalid(form)
    
    def get_success_url(self):
        return reverse_lazy('testing:test_detail', kwargs={'pk': self.object.pk})


class TestItemUpdateView(LoginRequiredMixin, UpdateView):
    """更新测试项"""
    model = TestItem
    template_name = 'testing/test_form.html'
    form_class = TestItemForm
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['tracker'].queryset = User.objects.filter(role__in=['fae', 'fae_leader'])
        return form
    
    def form_valid(self, form):
        # 获取原始数据
        old_instance = self.get_object()
        old_status = old_instance.status
        
        response = super().form_valid(form)
        
        # 创建日志
        new_status = form.instance.status
        
        # 收集变更的字段
        changed_fields = []
        detail_changes = []
        
        field_names = {
            'tracker': '跟踪人',
            'customer': '所属客户',
            'test_content': '测试内容',
            'status': '测试状态',
            'solution': '测试方案',
            'total_samples': '样品总数量',
            'passed_samples': '通过数量',
            'abnormal_samples_count': '异常数量',
            'start_date': '开始时间',
            'end_date': '结束时间',
        }
        
        for field, label in field_names.items():
            old_value = getattr(old_instance, field)
            new_value = getattr(form.instance, field)
            if old_value != new_value:
                changed_fields.append(label)
                # 获取显示值
                if field == 'test_content':
                    old_display = dict(TestItem.TEST_CONTENT_CHOICES).get(old_value, old_value)
                    new_display = dict(TestItem.TEST_CONTENT_CHOICES).get(new_value, new_value)
                elif field == 'status':
                    old_display = dict(TestItem.TEST_STATUS_CHOICES).get(old_value, old_value)
                    new_display = dict(TestItem.TEST_STATUS_CHOICES).get(new_value, new_value)
                elif field in ['tracker', 'customer']:
                    old_display = str(old_value) if old_value else '无'
                    new_display = str(new_value) if new_value else '无'
                elif field == 'solution':
                    old_display = old_value.solution_number if old_value else '无'
                    new_display = new_value.solution_number if new_value else '无'
                else:
                    old_display = str(old_value) if old_value is not None else ''
                    new_display = str(new_value) if new_value is not None else ''
                detail_changes.append(f"{label}: {old_display} → {new_display}")
        
        if changed_fields:
            action = f"更新任务（{', '.join(changed_fields)}）"
            comment = '；'.join(detail_changes)
        else:
            action = '更新任务'
            comment = ''
        
        TestItemLog.objects.create(
            test_item=self.object,
            operator=self.request.user,
            action=action,
            comment=comment,
            old_status=old_status if old_status != new_status else '',
            new_status=new_status if old_status != new_status else ''
        )
        
        # 记录项目时间线
        if self.object.project and changed_fields:
            from project.signals import record_project_activity
            record_project_activity(
                project=self.object.project,
                actor=self.request.user,
                action='update',
                instance=self.object,
                description='；'.join(detail_changes)
            )
        
        messages.success(self.request, '测试项更新成功')
        return response
    
    def get_success_url(self):
        return reverse_lazy('testing:test_detail', kwargs={'pk': self.object.pk})


class TestItemDeleteView(LoginRequiredMixin, DeleteView):
    """删除测试项"""
    model = TestItem
    template_name = 'testing/test_confirm_delete.html'
    success_url = reverse_lazy('testing:test_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, '测试项删除成功')
        return super().delete(request, *args, **kwargs)


class TestCommentCreateView(LoginRequiredMixin, CreateView):
    """添加测试评论"""
    model = TestComment
    form_class = TestCommentForm
    
    def form_valid(self, form):
        test = get_object_or_404(TestItem, pk=self.kwargs['pk'])
        form.instance.test = test
        form.instance.author = self.request.user
        messages.success(self.request, '评论添加成功')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('testing:test_detail', kwargs={'pk': self.kwargs['pk']})


class TestCommentDeleteView(LoginRequiredMixin, View):
    """删除测试评论（仅评论作者可删除）"""
    def post(self, request, pk):
        comment = get_object_or_404(TestComment, pk=pk)
        test_pk = comment.test.pk
        
        # 检查是否是评论作者
        if comment.author != request.user:
            messages.error(request, '您只能删除自己发布的评论')
            return redirect('testing:test_detail', pk=test_pk)
        
        comment.delete()
        messages.success(request, '评论已删除')
        return redirect('testing:test_detail', pk=test_pk)
