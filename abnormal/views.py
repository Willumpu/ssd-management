"""
异常样品管理视图
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View, ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone
from django.db import models
from django import forms
import os
from django.conf import settings
from django.core.files.base import ContentFile
from django.http import JsonResponse, HttpResponse
from .models import AbnormalSample, AbnormalSampleGroup, TestRecordEntry, AbnormalLogFile, AbnormalComment, AbnormalLog
from .forms import AbnormalCommentForm, AbnormalSampleForm, AbnormalSampleGroupForm
from fae.models import Customer, User
from testing.models import TestItem


class AbnormalSampleListView(LoginRequiredMixin, ListView):
    """异常样品列表"""
    model = AbnormalSample
    template_name = 'abnormal/abnormal_list.html'
    context_object_name = 'abnormals'
    
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
        
        # 按异常样品组分组（用于折叠展示）
        from collections import defaultdict
        queryset = self.get_queryset()
        grouped = defaultdict(list)
        ungrouped = []
        for sample in queryset:
            if sample.group:
                grouped[sample.group].append(sample)
            else:
                ungrouped.append(sample)
        context['grouped_abnormals'] = list(grouped.items())
        context['ungrouped_abnormals'] = ungrouped
        
        return context


class AbnormalSampleDetailView(LoginRequiredMixin, DetailView):
    """异常样品详情"""
    model = AbnormalSample
    template_name = 'abnormal/abnormal_detail.html'
    context_object_name = 'abnormal'
    
    def get_queryset(self):
        return super().get_queryset().select_related(
            'customer', 'project', 'test_item', 'solution', 'assignee', 'created_by'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['test_records'] = self.object.test_records.select_related('operator').all()
        context['log_files'] = self.object.log_files.all()
        context['log_choices'] = AbnormalSample.LOG_CHOICES
        context['comments'] = self.object.comments.select_related('author')
        context['logs'] = self.object.logs.select_related('operator')
        context['comment_form'] = AbnormalCommentForm()

        # 按 folder_name 分组，并生成显示用的格式化文件夹名
        from itertools import groupby
        sample = self.object
        log_file_groups = []
        for folder_name, items in groupby(self.object.log_files.all(), key=lambda x: x.folder_name):
            items = list(items)
            display_name = folder_name
            if folder_name:
                prefix = f"{sample.sample_number}_{items[0].log_type}_"
                if not folder_name.startswith(prefix):
                    display_name = prefix + folder_name
            log_file_groups.append({
                'folder_name': folder_name,
                'display_name': display_name,
                'files': items,
            })
        context['log_file_groups'] = log_file_groups
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
                # 自动填充负责人为测试项跟踪人
                if test_item.tracker:
                    form.fields['assignee'].initial = test_item.tracker
            except TestItem.DoesNotExist:
                pass
        
        # 如果从桑基图节点跳转过来，从节点关联的测试项自动填充
        sankey_node_id = self.request.GET.get('sankey_node')
        if sankey_node_id and not test_item_id:
            from testing.models import SankeyNode, TestItem
            try:
                node = SankeyNode.objects.select_related('test_item').get(pk=sankey_node_id)
                if node.test_item:
                    form.fields['test_item'].initial = node.test_item
                    if node.test_item.solution:
                        form.fields['solution'].initial = node.test_item.solution
                    form.fields['customer'].initial = node.test_item.customer
                    # 自动填充负责人为测试项跟踪人
                    if node.test_item.tracker:
                        form.fields['assignee'].initial = node.test_item.tracker
                # 子类节点/异常分类节点：自动将分类原因预设为异常概述
                if node.node_type in ('subcategory', 'abnormal_category') and node.category_reason:
                    form.initial['abnormal_summary'] = node.category_reason
            except (SankeyNode.DoesNotExist, TestItem.DoesNotExist):
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
        
        # 如果从桑基图节点跳转，且未设置项目，从节点的测试项继承项目
        sankey_node_id = self.request.GET.get('sankey_node') or self.request.POST.get('sankey_node')
        if sankey_node_id and not self.object.project:
            from testing.models import SankeyNode
            try:
                node = SankeyNode.objects.select_related('test_item__project').get(pk=sankey_node_id)
                if node.test_item and node.test_item.project:
                    self.object.project = node.test_item.project
                    self.object.save(update_fields=['project'])
            except SankeyNode.DoesNotExist:
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
        
        # 如果从桑基图节点跳转过来，自动关联到该节点
        sankey_node_id = self.request.GET.get('sankey_node') or self.request.POST.get('sankey_node')
        if sankey_node_id:
            from testing.models import SankeyNode
            try:
                node = SankeyNode.objects.get(pk=sankey_node_id)
                node.abnormal_samples.add(self.object)
            except SankeyNode.DoesNotExist:
                pass
        
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


class AbnormalSampleGroupListView(LoginRequiredMixin, ListView):
    """异常样品组列表"""
    model = AbnormalSampleGroup
    template_name = 'abnormal/group_list.html'
    context_object_name = 'groups'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = AbnormalSampleGroup.objects.all().select_related('customer', 'assignee')
        
        status = self.request.GET.get('status')
        priority = self.request.GET.get('priority')
        search = self.request.GET.get('search')
        
        if status:
            queryset = queryset.filter(status=status)
        if priority:
            queryset = queryset.filter(priority=priority)
        if search:
            queryset = queryset.filter(
                models.Q(group_number__icontains=search) |
                models.Q(customer__customer_code__icontains=search)
            )
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = AbnormalSampleGroup.STATUS_CHOICES
        context['priority_choices'] = AbnormalSampleGroup.PRIORITY_CHOICES
        context['current_status'] = self.request.GET.get('status', '')
        context['search_query'] = self.request.GET.get('search', '')
        return context


class AbnormalSampleGroupCreateView(LoginRequiredMixin, CreateView):
    """创建异常样品组（自动批量生成组员）"""
    model = AbnormalSampleGroup
    template_name = 'abnormal/group_form.html'
    form_class = AbnormalSampleGroupForm
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        # 如果从测试项跳转过来，自动填充相关信息
        test_item_id = self.request.GET.get('test_item')
        if test_item_id:
            from testing.models import TestItem
            try:
                test_item = TestItem.objects.select_related('customer', 'project', 'solution').get(pk=test_item_id)
                # 自动填充并限制字段
                if test_item.customer:
                    form.fields['customer'].queryset = form.fields['customer'].queryset.filter(pk=test_item.customer.pk)
                    form.initial['customer'] = test_item.customer.pk
                if test_item.project:
                    form.fields['project'].queryset = form.fields['project'].queryset.filter(pk=test_item.project.pk)
                    form.initial['project'] = test_item.project.pk
                if test_item.solution:
                    form.fields['solution'].queryset = form.fields['solution'].queryset.filter(pk=test_item.solution.pk)
                    form.initial['solution'] = test_item.solution.pk
                from testing.models import TestItem as TestItemModel
                form.fields['test_item'].queryset = TestItemModel.objects.filter(pk=test_item.pk)
                form.initial['test_item'] = test_item.pk
                # 自动填充负责人为测试项跟踪人
                if test_item.tracker:
                    form.fields['assignee'].queryset = form.fields['assignee'].queryset.filter(pk=test_item.tracker.pk)
                    form.initial['assignee'] = test_item.tracker.pk
                form.auto_from_test_item = True
            except TestItem.DoesNotExist:
                pass
        
        # 如果从桑基图子类节点跳转过来，从上游节点推导关联信息
        sankey_node_id = self.request.GET.get('sankey_node')
        if sankey_node_id:
            from testing.models import SankeyNode, TestItem
            try:
                node = SankeyNode.objects.select_related('test_item__customer', 'test_item__project', 'test_item__solution').get(pk=sankey_node_id)
                # 如果是子类节点且没有直接关联测试项，去上游节点查找
                target_node = node
                if node.node_type == 'subcategory' and not node.test_item:
                    upstream_edge = node.incoming_edges.select_related('source_node__test_item__customer', 'source_node__test_item__project', 'source_node__test_item__solution').first()
                    if upstream_edge and upstream_edge.source_node:
                        target_node = upstream_edge.source_node
                
                # 自动填充客户
                if target_node.test_item and target_node.test_item.customer:
                    form.fields['customer'].queryset = form.fields['customer'].queryset.filter(pk=target_node.test_item.customer.pk)
                    form.initial['customer'] = target_node.test_item.customer.pk
                # 自动填充项目
                if target_node.test_item and target_node.test_item.project:
                    form.fields['project'].queryset = form.fields['project'].queryset.filter(pk=target_node.test_item.project.pk)
                    form.initial['project'] = target_node.test_item.project.pk
                # 自动填充方案
                if target_node.test_item and target_node.test_item.solution:
                    form.fields['solution'].queryset = form.fields['solution'].queryset.filter(pk=target_node.test_item.solution.pk)
                    form.initial['solution'] = target_node.test_item.solution.pk
                # 自动填充测试项
                if target_node.test_item:
                    form.fields['test_item'].queryset = TestItem.objects.filter(pk=target_node.test_item.pk)
                    form.initial['test_item'] = target_node.test_item.pk
                    # 自动填充负责人为测试项跟踪人
                    if target_node.test_item.tracker:
                        form.fields['assignee'].queryset = form.fields['assignee'].queryset.filter(pk=target_node.test_item.tracker.pk)
                        form.initial['assignee'] = target_node.test_item.tracker.pk
                # 自动填充数量（子类节点的样品数量）
                total_count = self.request.GET.get('total_count')
                if total_count:
                    form.initial['total_count'] = int(total_count)
                elif node.quantity and node.quantity > 0:
                    form.initial['total_count'] = node.quantity
                # 子类节点/异常分类节点：自动将分类原因预设为异常概述
                if node.node_type in ('subcategory', 'abnormal_category') and node.category_reason:
                    form.initial['abnormal_summary'] = node.category_reason
                form.auto_from_sankey_node = True
            except SankeyNode.DoesNotExist:
                pass
        
        return form
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        total_count = form.cleaned_data.get('total_count', 1)
        
        # 先保存组
        response = super().form_valid(form)
        group = self.object
        
        # 批量创建异常样品
        for i in range(total_count):
            sample = AbnormalSample(
                customer=group.customer,
                project=group.project,
                solution=group.solution,
                priority=group.priority,
                status=group.status,
                assignee=group.assignee,
                test_item=group.test_item,
                group=group,
                abnormal_summary=group.abnormal_summary,
                abnormal_description=group.abnormal_description,
                created_by=self.request.user,
            )
            sample.save()
            
            # 如果组关联了测试项，自动创建关联
            if group.test_item:
                from testing.models import TestAbnormalRelation
                TestAbnormalRelation.objects.get_or_create(
                    test_item=group.test_item,
                    abnormal_sample=sample
                )
        
        # 更新组的实际数量
        group.total_count = group.samples.count()
        group.save(update_fields=['total_count'])
        
        # 如果从桑基图节点跳转过来，将组内所有样品绑定到该节点
        sankey_node_id = self.request.GET.get('sankey_node') or self.request.POST.get('sankey_node')
        if sankey_node_id:
            from testing.models import SankeyNode
            try:
                node = SankeyNode.objects.get(pk=sankey_node_id)
                for sample in group.samples.all():
                    node.abnormal_samples.add(sample)
            except SankeyNode.DoesNotExist:
                pass
        
        messages.success(self.request, f'异常样品组 {group.group_number} 创建成功，已自动生成 {total_count} 个样品')
        return response
    
    def get_success_url(self):
        return reverse_lazy('abnormal:group_detail', kwargs={'pk': self.object.pk})


class AbnormalSampleGroupDetailView(LoginRequiredMixin, DetailView):
    """异常样品组详情"""
    model = AbnormalSampleGroup
    template_name = 'abnormal/group_detail.html'
    context_object_name = 'group'
    
    def get_queryset(self):
        return super().get_queryset().select_related(
            'customer', 'test_item', 'solution', 'assignee', 'created_by'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['samples'] = self.object.samples.select_related('assignee').all()
        from fae.models import User
        context['assignee_choices'] = User.objects.filter(role__in=['fae', 'fae_leader']).order_by('username')
        context['log_choices'] = AbnormalSample.LOG_CHOICES
        return context


class AbnormalSampleGroupUpdateView(LoginRequiredMixin, UpdateView):
    """更新异常样品组"""
    model = AbnormalSampleGroup
    template_name = 'abnormal/group_form.html'
    form_class = AbnormalSampleGroupForm
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # 编辑时显示数量，允许修改
        if self.object.pk:
            current_count = self.object.samples.count()
            form.fields['total_count'].widget = forms.NumberInput(
                attrs={'min': 1, 'class': 'w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-slate-200 focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500/50'}
            )
            form.fields['total_count'].help_text = f'当前有 {current_count} 个样品，减少时会自动删除最后创建的未编辑样品'
        return form
    
    def form_valid(self, form):
        group = self.object
        old_count = group.samples.count()
        new_count = form.cleaned_data.get('total_count', old_count)
        
        response = super().form_valid(form)
        
        # 处理数量增加：自动创建新样品
        if new_count > old_count:
            added = 0
            for i in range(new_count - old_count):
                sample = AbnormalSample(
                    customer=group.customer,
                    project=group.project,
                    solution=group.solution,
                    priority=group.priority,
                    status=group.status,
                    assignee=group.assignee,
                    test_item=group.test_item,
                    group=group,
                    abnormal_summary=group.abnormal_summary,
                    abnormal_description=group.abnormal_description,
                    created_by=self.request.user,
                )
                sample.save()
                
                # 如果组关联了测试项，自动创建关联
                if group.test_item:
                    from testing.models import TestAbnormalRelation
                    TestAbnormalRelation.objects.get_or_create(
                        test_item=group.test_item,
                        abnormal_sample=sample
                    )
                added += 1
            
            # 更新组的实际数量
            group.total_count = group.samples.count()
            group.save(update_fields=['total_count'])
            
            messages.success(
                self.request,
                f'异常样品组 {group.group_number} 更新成功，已新增 {added} 个样品'
            )
        
        # 处理数量减少：自动删除最后创建的未编辑样品
        elif new_count < old_count:
            need_delete = old_count - new_count
            # 找出未编辑过的样品，按创建时间倒序（最后创建的优先删除）
            deletable = group.samples.filter(
                is_edited_individually=False
            ).order_by('-created_at')
            
            deleted = 0
            skipped = 0
            for sample in deletable[:need_delete]:
                sample.delete()
                deleted += 1
            
            # 更新组的实际数量
            group.total_count = group.samples.count()
            group.save(update_fields=['total_count'])
            
            remaining = need_delete - deleted
            if remaining > 0:
                messages.warning(
                    self.request,
                    f'异常样品组 {group.group_number} 已更新，删除了 {deleted} 个未编辑样品，'
                    f'还有 {remaining} 个需减少但因已被单独编辑而保留，请到详情页手动处理'
                )
            else:
                messages.success(
                    self.request,
                    f'异常样品组 {group.group_number} 更新成功，已删除 {deleted} 个样品'
                )
        
        else:
            messages.success(self.request, f'异常样品组 {group.group_number} 更新成功')
        
        return response
    
    def get_success_url(self):
        return reverse_lazy('abnormal:group_detail', kwargs={'pk': self.object.pk})


class AbnormalSampleGroupDeleteView(LoginRequiredMixin, DeleteView):
    """删除异常样品组"""
    model = AbnormalSampleGroup
    template_name = 'abnormal/group_confirm_delete.html'
    context_object_name = 'group'
    success_url = reverse_lazy('abnormal:group_list')
    
    def delete(self, request, *args, **kwargs):
        group = self.get_object()
        messages.success(request, f'异常样品组 {group.group_number} 已删除')
        return super().delete(request, *args, **kwargs)


class AbnormalSampleGroupBulkEditView(LoginRequiredMixin, View):
    """批量编辑组内异常样品"""
    def post(self, request, pk):
        group = get_object_or_404(AbnormalSampleGroup, pk=pk)
        sample_ids = request.POST.getlist('sample_ids')
        action = request.POST.get('bulk_action')
        
        if not sample_ids:
            messages.error(request, '请先选择要编辑的样品')
            return redirect('abnormal:group_detail', pk=pk)
        
        samples = group.samples.filter(pk__in=sample_ids)
        
        if action == 'sync_all':
            # 同步组属性到全部样品
            samples.update(
                solution=group.solution,
                priority=group.priority,
                status=group.status,
                assignee=group.assignee,
                abnormal_description=group.abnormal_description,
            )
            messages.success(request, f'已将组属性同步到 {samples.count()} 个样品')
        
        elif action == 'sync_unedited':
            # 只同步未单独编辑过的样品
            unedited = samples.filter(is_edited_individually=False)
            unedited.update(
                solution=group.solution,
                priority=group.priority,
                status=group.status,
                assignee=group.assignee,
                abnormal_description=group.abnormal_description,
            )
            messages.success(request, f'已将组属性同步到 {unedited.count()} 个未编辑样品')
        
        elif action == 'update_status':
            new_status = request.POST.get('new_status')
            if new_status in dict(AbnormalSample.STATUS_CHOICES):
                samples.update(status=new_status)
                messages.success(request, f'已更新 {samples.count()} 个样品的状态')
        
        elif action == 'update_priority':
            new_priority = request.POST.get('new_priority')
            if new_priority in dict(AbnormalSample.PRIORITY_CHOICES):
                samples.update(priority=new_priority)
                messages.success(request, f'已更新 {samples.count()} 个样品的优先级')
        
        elif action == 'update_assignee':
            assignee_id = request.POST.get('new_assignee')
            if assignee_id:
                samples.update(assignee_id=assignee_id)
                messages.success(request, f'已更新 {samples.count()} 个样品的负责人')
        
        return redirect('abnormal:group_detail', pk=pk)


class AbnormalSampleGroupBatchUploadLogView(LoginRequiredMixin, View):
    """批量上传日志文件到异常样品组，拖动时通过方向选择每个节点的日志类型"""
    def post(self, request, pk):
        group = get_object_or_404(AbnormalSampleGroup, pk=pk)
        log_files = request.FILES.getlist('log_files')

        if not log_files:
            messages.error(request, '请选择要上传的日志文件')
            return redirect('abnormal:group_detail', pk=pk)

        samples = {str(s.pk): s for s in group.samples.all()}
        matched_count = 0
        skipped_count = 0

        for index, log_file in enumerate(log_files):
            sample_pk = request.POST.get(f'sample_for_{index}')
            file_log_type = request.POST.get(f'log_type_for_{index}')
            folder_name = request.POST.get(f'folder_for_{index}', '')
            if not sample_pk or not file_log_type:
                skipped_count += 1
                continue
            sample = samples.get(sample_pk)
            if not sample:
                skipped_count += 1
                continue

            # 生成规范文件名：样品编号_日志类型_原文件名
            base_name, ext = os.path.splitext(log_file.name)
            safe_name = f"{sample.sample_number}_{file_log_type}_{base_name}{ext}"

            try:
                AbnormalLogFile.objects.create(
                    abnormal_sample=sample,
                    log_type=file_log_type,
                    folder_name=folder_name,
                    file=ContentFile(log_file.read(), name=safe_name),
                    uploaded_by=request.user
                )
                matched_count += 1
            except Exception as e:
                messages.error(request, f'文件 {log_file.name} 上传失败：{str(e)}')

        if matched_count:
            messages.success(request, f'成功上传 {matched_count} 个日志文件')
        if skipped_count:
            messages.warning(request, f'{skipped_count} 个文件未匹配样品或日志类型，已跳过')

        return redirect('abnormal:group_detail', pk=pk)


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
        
        # 标记为已单独编辑
        form.instance.is_edited_individually = True
        
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
        
        # 记录项目时间线（仅状态变更时）
        if self.object.project and old_instance.status != self.object.status:
            from project.signals import record_project_activity
            status_dict = dict(AbnormalSample.STATUS_CHOICES)
            old_status_display = status_dict.get(old_instance.status, old_instance.status)
            new_status_display = status_dict.get(self.object.status, self.object.status)
            record_project_activity(
                project=self.object.project,
                actor=self.request.user,
                action='status_change',
                instance=self.object,
                description=f"状态：{old_status_display} → {new_status_display}"
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
    """上传日志文件/文件夹到 NAS（通过 Django 默认存储，MEDIA_ROOT 指向 NAS）"""
    def post(self, request, pk):
        abnormal_sample = get_object_or_404(AbnormalSample, pk=pk)
        log_type = request.POST.get('log_type')
        description = request.POST.get('description', '')

        if not log_type:
            messages.error(request, '请选择日志类型')
            return redirect('abnormal:abnormal_detail', pk=pk)

        # rdt_all_flush 类型上传整个文件夹
        if log_type == 'rdt_all_flush':
            log_files = request.FILES.getlist('log_files')
            if not log_files:
                messages.error(request, '请选择要上传的文件夹')
                return redirect('abnormal:abnormal_detail', pk=pk)

            folder_name = ''
            first_path = getattr(log_files[0], 'webkitRelativePath', None) or log_files[0].name
            parts = first_path.split('/')
            if len(parts) > 1:
                folder_name = parts[0]
            if not folder_name:
                folder_name = 'folder'

            solution_name = abnormal_sample.solution.solution_number if abnormal_sample.solution else 'no-solution'

            created = 0
            for log_file in log_files:
                try:
                    base_name, ext = os.path.splitext(log_file.name)
                    safe_name = f"{abnormal_sample.sample_number}_{log_type}_{base_name}{ext}"
                    AbnormalLogFile.objects.create(
                        abnormal_sample=abnormal_sample,
                        log_type=log_type,
                        folder_name=folder_name,
                        file=ContentFile(log_file.read(), name=safe_name),
                        description=description,
                        uploaded_by=request.user
                    )
                    created += 1
                except Exception as e:
                    messages.error(request, f'文件 {log_file.name} 上传失败：{str(e)}')
            if created:
                messages.success(request, f'成功上传 {created} 个日志文件')
            return redirect('abnormal:abnormal_detail', pk=pk)

        # 其他类型上传单个文件
        log_file = request.FILES.get('log_file')
        if not log_file:
            messages.error(request, '请选择要上传的文件')
            return redirect('abnormal:abnormal_detail', pk=pk)

        try:
            # 生成规范文件名：样品编号_日志类型_原文件名
            base_name, ext = os.path.splitext(log_file.name)
            safe_name = f"{abnormal_sample.sample_number}_{log_type}_{base_name}{ext}"
            log_file.name = safe_name

            AbnormalLogFile.objects.create(
                abnormal_sample=abnormal_sample,
                log_type=log_type,
                file=log_file,
                description=description,
                uploaded_by=request.user
            )
            messages.success(request, '日志文件上传成功')
        except Exception as e:
            messages.error(request, f'上传失败：{str(e)}')

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


def _get_cache_path(log_file):
    """获取日志文件的本地缓存路径（OSS文件首次查看时下载到本地缓存）"""
    cache_dir = str(settings.LOG_CACHE_DIR)
    os.makedirs(cache_dir, exist_ok=True)
    
    if log_file.file and log_file.file.path:
        if os.path.exists(log_file.file.path):
            return log_file.file.path
        return None
    elif log_file.file_url:
        safe_name = f"{log_file.pk}_{log_file.filename}"
        cache_path = os.path.join(cache_dir, safe_name)
        if os.path.exists(cache_path):
            return cache_path
        try:
            from utils.oss import get_oss_bucket
            import urllib.parse
            path = urllib.parse.urlparse(log_file.file_url).path.lstrip('/')
            bucket = get_oss_bucket()
            bucket.get_object_to_file(path, cache_path)
            return cache_path
        except Exception:
            return None
    return None


def _is_text_file(path):
    """检测文件是否为文本文件"""
    with open(path, 'rb') as f:
        sample = f.read(4096)
    for enc in ('utf-8', 'gbk'):
        try:
            sample.decode(enc)
            return True
        except UnicodeDecodeError:
            continue
    decoded = sample.decode('utf-8', errors='replace')
    return decoded.count('\ufffd') / max(len(decoded), 1) <= 0.05


class AbnormalLogFileView(LoginRequiredMixin, View):
    """日志分析器页面：后端只负责把 OSS 文件拉到本地缓存，前端直接 fetch 文件内容"""
    MAX_SIZE = 20 * 1024 * 1024
    
    def get(self, request, pk):
        log_file = get_object_or_404(AbnormalLogFile, pk=pk)
        cache_path = _get_cache_path(log_file)
        if not cache_path:
            return HttpResponse('文件暂不可用，请稍后重试。', content_type='text/plain; charset=utf-8', status=400)
        
        file_size = os.path.getsize(cache_path)
        if file_size > self.MAX_SIZE:
            return HttpResponse('文件超过 20MB，不支持在线查看，请下载后打开。', content_type='text/plain; charset=utf-8')
        
        if not _is_text_file(cache_path):
            return HttpResponse('此文件为二进制文件，不支持在线查看，请下载后打开。', content_type='text/plain; charset=utf-8')
        
        # 计算前端可直接 fetch 的文件 URL
        if log_file.file and log_file.file.path:
            file_url = log_file.file.url
        else:
            # OSS 缓存文件，构造 media URL
            file_url = settings.MEDIA_URL + 'cache/logs/' + f"{log_file.pk}_{log_file.filename}"
        
        return render(request, 'abnormal/log_viewer.html', {
            'log_file': log_file,
            'file_url': file_url,
            'file_size': file_size,
        })


class AbnormalLogFileDeleteView(LoginRequiredMixin, View):
    """删除日志文件（同时删除 OSS 上的文件和本地缓存）"""
    def post(self, request, pk):
        log_file = get_object_or_404(AbnormalLogFile, pk=pk)
        abnormal_pk = log_file.abnormal_sample.pk
        
        try:
            # 删除 OSS 文件
            if log_file.file_url:
                from utils.oss import get_oss_bucket
                import urllib.parse
                path = urllib.parse.urlparse(log_file.file_url).path.lstrip('/')
                bucket = get_oss_bucket()
                bucket.delete_object(path)
            
            # 删除本地缓存
            if log_file.file_url:
                cache_dir = str(settings.LOG_CACHE_DIR)
                safe_name = f"{log_file.pk}_{log_file.filename}"
                cache_path = os.path.join(cache_dir, safe_name)
                if os.path.exists(cache_path):
                    try:
                        os.remove(cache_path)
                    except Exception:
                        pass
            
            # 删除本地文件和数据库记录
            if log_file.file:
                log_file.file.delete(save=False)
            log_file.delete()
            messages.success(request, '日志文件已删除')
        except Exception as e:
            messages.error(request, f'删除失败：{str(e)}')
        
        return redirect('abnormal:abnormal_detail', pk=abnormal_pk)


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



class AbnormalSampleAPIListView(LoginRequiredMixin, View):
    """API：获取异常样品列表（用于桑基图关联选择）"""
    def get(self, request):
        fae_task_id = request.GET.get('fae_task_id')
        queryset = AbnormalSample.objects.all().select_related('customer')
        if fae_task_id:
            from fae.models import FAETask
            from testing.models import SankeyNode
            try:
                task = FAETask.objects.get(pk=fae_task_id)
                # 获取该任务下所有有 test_item 的桑基图节点对应的测试项 ID
                task_test_item_ids = SankeyNode.objects.filter(
                    fae_task=task,
                    test_item__isnull=False
                ).values_list('test_item_id', flat=True).distinct()
                # 只返回与该任务测试项关联，或已关联到该任务桑基图节点的异常样品
                queryset = queryset.filter(
                    models.Q(test_item_id__in=task_test_item_ids) |
                    models.Q(sankey_nodes__fae_task=task)
                ).distinct()
            except FAETask.DoesNotExist:
                pass
        result = []
        for a in queryset.order_by('-created_at').select_related('group'):
            result.append({
                'id': a.id,
                'sample_number': a.sample_number,
                'status': a.status,
                'status_display': a.get_status_display(),
                'priority': a.priority,
                'group_id': a.group_id,
                'group_number': a.group.group_number if a.group else None,
            })
        return JsonResponse({'abnormals': result})


class AbnormalSampleGroupAPIListView(LoginRequiredMixin, View):
    """API：获取异常样品组列表（用于桑基图关联选择）"""
    def get(self, request):
        fae_task_id = request.GET.get('fae_task_id')
        queryset = AbnormalSampleGroup.objects.all().select_related('customer')
        if fae_task_id:
            from fae.models import FAETask
            from testing.models import SankeyNode
            try:
                task = FAETask.objects.get(pk=fae_task_id)
                # 获取该任务下所有有 test_item 的桑基图节点对应的测试项 ID
                task_test_item_ids = SankeyNode.objects.filter(
                    fae_task=task,
                    test_item__isnull=False
                ).values_list('test_item_id', flat=True).distinct()
                # 只返回与该任务测试项关联，或已关联到该任务桑基图节点的异常样品组
                queryset = queryset.filter(
                    models.Q(test_item_id__in=task_test_item_ids) |
                    models.Q(samples__sankey_nodes__fae_task=task)
                ).distinct()
            except FAETask.DoesNotExist:
                pass
        result = []
        for g in queryset.order_by('-created_at'):
            result.append({
                'id': g.id,
                'group_number': g.group_number,
                'status': g.status,
                'status_display': g.get_status_display(),
                'priority': g.priority,
                'sample_count': g.samples.count(),
            })
        return JsonResponse({'groups': result})
