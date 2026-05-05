"""
异常样品管理视图
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View, ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone
from django.db import models
from .models import AbnormalSample, TestRecordEntry, AbnormalLogFile, AbnormalComment, AbnormalLog
from .forms import AbnormalCommentForm, AbnormalSampleForm
from fae.models import Customer, User
from testing.models import TestItem


class AbnormalSampleListView(LoginRequiredMixin, ListView):
    """异常样品列表"""
    model = AbnormalSample
    template_name = 'abnormal/abnormal_list.html'
    context_object_name = 'abnormals'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = AbnormalSample.objects.all().select_related('customer', 'assignee')
        
        status = self.request.GET.get('status')
        priority = self.request.GET.get('priority')
        search = self.request.GET.get('search')
        
        if status:
            queryset = queryset.filter(status=status)
        if priority:
            queryset = queryset.filter(priority=priority)
        if search:
            queryset = queryset.filter(
                models.Q(sample_number__icontains=search) |
                models.Q(customer__customer_code__icontains=search) |
                models.Q(abnormal_description__icontains=search)
            )
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = AbnormalSample.STATUS_CHOICES
        context['priority_choices'] = AbnormalSample.PRIORITY_CHOICES
        context['current_status'] = self.request.GET.get('status', '')
        context['search_query'] = self.request.GET.get('search', '')
        # 统计数据
        context['total_count'] = AbnormalSample.objects.count()
        context['pending_count'] = AbnormalSample.objects.filter(status='pending_analysis').count()
        context['processing_count'] = AbnormalSample.objects.filter(status='retesting').count()
        context['resolved_count'] = AbnormalSample.objects.filter(status='resolved').count()
        return context


class AbnormalSampleDetailView(LoginRequiredMixin, DetailView):
    """异常样品详情"""
    model = AbnormalSample
    template_name = 'abnormal/abnormal_detail.html'
    context_object_name = 'abnormal'
    
    def get_queryset(self):
        return super().get_queryset().select_related(
            'customer', 'test_item', 'solution', 'assignee', 'created_by'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['test_records'] = self.object.test_records.select_related('operator').all()
        context['log_files'] = self.object.log_files.all()
        context['log_choices'] = AbnormalSample.LOG_CHOICES
        context['comments'] = self.object.comments.select_related('author')
        context['logs'] = self.object.logs.select_related('operator')
        context['comment_form'] = AbnormalCommentForm()
        return context


class AbnormalSampleCreateView(LoginRequiredMixin, CreateView):
    """创建异常样品记录"""
    model = AbnormalSample
    template_name = 'abnormal/abnormal_form.html'
    form_class = AbnormalSampleForm
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['assignee'].queryset = User.objects.filter(role__in=['fae', 'fae_leader'])
        form.fields['customer'].queryset = Customer.objects.all().order_by('customer_code')
        from solution.models import Solution
        form.fields['solution'].queryset = Solution.objects.all().order_by('-created_at')
        
        # 如果从项目跳转过来，自动填充项目
        project_id = self.request.GET.get('project')
        if project_id:
            from project.models import Project
            form.fields['project'].queryset = Project.objects.filter(pk=project_id)
            form.initial['project'] = int(project_id)
            # project 字段在模板中根据 request.GET.project 条件隐藏/显示
        
        # 如果从测试项跳转过来，自动填充关联测试项
        test_item_id = self.request.GET.get('test_item')
        if test_item_id:
            from testing.models import TestItem
            try:
                test_item = TestItem.objects.get(pk=test_item_id)
                form.fields['test_item'].initial = test_item
                # 如果有方案，也自动填充方案
                if test_item.solution:
                    form.fields['solution'].initial = test_item.solution
                # 自动填充客户
                form.fields['customer'].initial = test_item.customer
            except TestItem.DoesNotExist:
                pass
        
        return form
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.status = 'pending_analysis'
        
        # 先保存表单数据
        response = super().form_valid(form)
        
        # 如果从测试项跳转过来，且测试项归属到某个项目，异常样品也自动归属到同一项目
        test_item_id = self.request.GET.get('test_item') or self.request.POST.get('test_item')
        if test_item_id and not self.object.project:
            from testing.models import TestItem
            try:
                test_item = TestItem.objects.get(pk=test_item_id)
                if test_item.project:
                    self.object.project = test_item.project
                    self.object.save(update_fields=['project'])
            except TestItem.DoesNotExist:
                pass
        
        # 记录项目时间线（如果从测试项跳转并继承了项目）
        if self.object.project:
            from project.signals import record_project_activity, build_create_description
            record_project_activity(
                project=self.object.project,
                actor=self.request.user,
                action='create',
                instance=self.object,
                description=build_create_description(self.object, 'abnormal_sample')
            )
        
        # 处理日志获取多选（如果有的话）
        logs_collected = self.request.POST.getlist('logs_collected')
        if logs_collected:
            self.object.logs_collected = logs_collected
            self.object.save(update_fields=['logs_collected'])
        
        # 创建操作日志
        AbnormalLog.objects.create(
            abnormal_sample=self.object,
            operator=self.request.user,
            action='创建异常样品',
            new_status='pending_analysis',
            comment=f'客户: {self.object.customer.customer_code}'
        )
        
        messages.success(self.request, '异常样品登记成功')
        return response
    
    def get_success_url(self):
        return reverse_lazy('abnormal:abnormal_detail', kwargs={'pk': self.object.pk})


class AbnormalSampleUpdateView(LoginRequiredMixin, UpdateView):
    """更新异常样品记录"""
    model = AbnormalSample
    template_name = 'abnormal/abnormal_form.html'
    form_class = AbnormalSampleForm
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['assignee'].queryset = User.objects.filter(role__in=['fae', 'fae_leader'])
        form.fields['customer'].queryset = Customer.objects.all().order_by('customer_code')
        from solution.models import Solution
        form.fields['solution'].queryset = Solution.objects.all().order_by('-created_at')
        return form
    
    def form_valid(self, form):
        # 获取编辑前的值（关键：用get_object()获取原始实例）
        old_instance = self.get_object()
        
        response = super().form_valid(form)
        
        # 如果状态变为已解决，记录解决时间
        if self.object.status == 'resolved' and old_instance.status != 'resolved':
            self.object.resolved_at = timezone.now()
            self.object.save()
        
        # 处理日志获取多选
        logs_collected = self.request.POST.getlist('logs_collected')
        if set(logs_collected) != set(self.object.logs_collected or []):
            self.object.logs_collected = logs_collected
            self.object.save(update_fields=['logs_collected'])
        
        # 检测变更的字段
        changed_fields = []
        detail_changes = []
        
        # 字段映射：字段名 -> 显示名称
        field_display_names = {
            'customer': '客户',
            'priority': '优先级',
            'solution': '样品方案',
            'abnormal_description': '异常描述',
            'assignee': '分析负责人',
            'test_item': '所属测试',
        }
        
        # 检测基本字段变更
        for field, label in field_display_names.items():
            old_value = getattr(old_instance, field)
            new_value = getattr(self.object, field)
            
            # ForeignKey 比较 ID
            if field in ['customer', 'assignee', 'solution', 'test_item']:
                old_id = old_value.id if old_value else None
                new_id = new_value.id if new_value else None
                changed = old_id != new_id
            elif field == 'abnormal_description':
                # 富文本字段，去除HTML标签后比较
                import re
                old_clean = re.sub(r'<[^>]+>', '', str(old_value or '')).strip()
                new_clean = re.sub(r'<[^>]+>', '', str(new_value or '')).strip()
                changed = old_clean != new_clean
            else:
                changed = old_value != new_value
            
            if changed:
                changed_fields.append(label)
                # 获取显示值
                if field == 'customer':
                    old_display = old_value.customer_code if old_value else '无'
                    new_display = new_value.customer_code if new_value else '无'
                elif field == 'assignee':
                    old_display = old_value.username if old_value else '无'
                    new_display = new_value.username if new_value else '无'
                elif field == 'solution':
                    old_display = str(old_value) if old_value else '无'
                    new_display = str(new_value) if new_value else '无'
                elif field == 'test_item':
                    old_display = str(old_value) if old_value else '无'
                    new_display = str(new_value) if new_value else '无'
                elif field == 'priority':
                    priority_map = dict(AbnormalSample.PRIORITY_CHOICES)
                    old_display = priority_map.get(old_value, old_value)
                    new_display = priority_map.get(new_value, new_value)
                elif field == 'abnormal_description':
                    import re
                    old_text = re.sub(r'<[^>]+>', '', str(old_value or '')).strip()
                    new_text = re.sub(r'<[^>]+>', '', str(new_value or '')).strip()
                    old_display = (old_text[:30] + '...') if old_text else '无'
                    new_display = (new_text[:30] + '...') if new_text else '无'
                else:
                    old_display = str(old_value) if old_value is not None else '无'
                    new_display = str(new_value) if new_value is not None else '无'
                detail_changes.append(f"{label}: {old_display} → {new_display}")
        
        # 检测日志获取变化
        old_logs = old_instance.logs_collected or []
        new_logs = self.object.logs_collected or []
        if set(old_logs) != set(new_logs):
            changed_fields.append('日志获取')
            old_logs_str = ', '.join(old_logs) if old_logs else '无'
            new_logs_str = ', '.join(new_logs) if new_logs else '无'
            detail_changes.append(f"日志获取: {old_logs_str} → {new_logs_str}")
        
        # 构建操作描述
        if changed_fields:
            action = f"更新异常样品（{', '.join(changed_fields)}）"
            comment = '; '.join(detail_changes)
        else:
            action = '编辑了异常样品'
            comment = ''
        
        # 创建日志
        AbnormalLog.objects.create(
            abnormal_sample=self.object,
            operator=self.request.user,
            action=action,
            comment=comment,
            new_status=self.object.status,
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
        
        messages.success(self.request, '异常样品记录更新成功')
        return response
    
    def get_success_url(self):
        return reverse_lazy('abnormal:abnormal_detail', kwargs={'pk': self.object.pk})


class TestRecordEntryCreateView(LoginRequiredMixin, CreateView):
    """添加测试记录条目"""
    model = TestRecordEntry
    fields = ['content']
    template_name = 'abnormal/test_record_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['abnormal'] = get_object_or_404(AbnormalSample, pk=self.kwargs['pk'])
        return context
    
    def form_valid(self, form):
        abnormal_sample = get_object_or_404(AbnormalSample, pk=self.kwargs['pk'])
        form.instance.abnormal_sample = abnormal_sample
        form.instance.operator = self.request.user
        
        response = super().form_valid(form)
        messages.success(self.request, '测试记录添加成功')
        return response
    
    def get_success_url(self):
        return reverse_lazy('abnormal:abnormal_detail', kwargs={'pk': self.kwargs['pk']})


class AbnormalLogFileCreateView(LoginRequiredMixin, View):
    """上传日志文件"""
    def post(self, request, pk):
        abnormal_sample = get_object_or_404(AbnormalSample, pk=pk)
        log_file = request.FILES.get('file')
        log_type = request.POST.get('log_type')
        description = request.POST.get('description', '')
        
        if log_file:
            AbnormalLogFile.objects.create(
                abnormal_sample=abnormal_sample,
                log_type=log_type,
                file=log_file,
                description=description,
                uploaded_by=request.user
            )
            messages.success(request, '日志文件上传成功')
        else:
            messages.error(request, '请选择要上传的文件')
        
        return redirect('abnormal:abnormal_detail', pk=pk)


class AbnormalCommentCreateView(LoginRequiredMixin, CreateView):
    """添加异常样品评论"""
    model = AbnormalComment
    form_class = AbnormalCommentForm
    
    def form_valid(self, form):
        abnormal = get_object_or_404(AbnormalSample, pk=self.kwargs['pk'])
        form.instance.abnormal_sample = abnormal
        form.instance.author = self.request.user
        messages.success(self.request, '评论添加成功')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('abnormal:abnormal_detail', kwargs={'pk': self.kwargs['pk']})


class AbnormalCommentDeleteView(LoginRequiredMixin, View):
    """删除异常样品评论（仅评论作者可删除）"""
    def post(self, request, pk):
        comment = get_object_or_404(AbnormalComment, pk=pk)
        abnormal_pk = comment.abnormal_sample.pk
        
        # 检查是否是评论作者
        if comment.author != request.user:
            messages.error(request, '您只能删除自己发布的评论')
            return redirect('abnormal:abnormal_detail', pk=abnormal_pk)
        
        comment.delete()
        messages.success(request, '评论已删除')
        return redirect('abnormal:abnormal_detail', pk=abnormal_pk)


class AbnormalSampleChangeStatusView(LoginRequiredMixin, View):
    """变更异常样品状态"""
    def post(self, request, pk):
        abnormal = get_object_or_404(AbnormalSample, pk=pk)
        new_status = request.POST.get('status')
        
        if new_status in dict(AbnormalSample.STATUS_CHOICES):
            old_status = abnormal.status
            old_status_display = abnormal.get_status_display()
            
            abnormal.status = new_status
            abnormal.save()
            
            new_status_display = abnormal.get_status_display()
            
            # 创建操作日志
            AbnormalLog.objects.create(
                abnormal_sample=abnormal,
                operator=request.user,
                action=f"状态变更: {old_status_display} → {new_status_display}",
                new_status=new_status
            )
            
            # 记录项目时间线
            if abnormal.project:
                from project.signals import record_project_activity
                record_project_activity(
                    project=abnormal.project,
                    actor=request.user,
                    action='status_change',
                    instance=abnormal,
                    description=f"状态：{old_status_display} → {new_status_display}"
                )
            
            messages.success(request, f'状态已更新为 {new_status_display}')
        else:
            messages.error(request, '无效的状态')
        
        return redirect('abnormal:abnormal_detail', pk=pk)
