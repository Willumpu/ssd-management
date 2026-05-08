"""
研发需求管理视图
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View, ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone
from django.db import models
import re
from .models import RDRequirement, RequirementProgress, RequirementAttachment, RequirementComment, RequirementLog
from .forms import RequirementCommentForm, RequirementProgressForm, RDRequirementForm
from fae.models import User, Customer, FAETask


class RDRequirementListView(LoginRequiredMixin, ListView):
    """研发需求列表"""
    model = RDRequirement
    template_name = 'rd_requirement/requirement_list.html'
    context_object_name = 'requirements'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('assignee', 'related_customer')
        
        requirement_type = self.request.GET.get('type')
        priority = self.request.GET.get('priority')
        status = self.request.GET.get('status')
        search = self.request.GET.get('search')
        
        if requirement_type:
            queryset = queryset.filter(requirement_type=requirement_type)
        if priority:
            queryset = queryset.filter(priority=priority)
        if status:
            queryset = queryset.filter(status=status)
        if search:
            queryset = queryset.filter(
                models.Q(requirement_number__icontains=search) |
                models.Q(title__icontains=search)
            )
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['type_choices'] = RDRequirement.REQUIREMENT_TYPE_CHOICES
        context['priority_choices'] = RDRequirement.PRIORITY_CHOICES
        context['status_choices'] = RDRequirement.STATUS_CHOICES
        return context


class RDRequirementDetailView(LoginRequiredMixin, DetailView):
    """研发需求详情"""
    model = RDRequirement
    template_name = 'rd_requirement/requirement_detail.html'
    context_object_name = 'requirement'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['progress_logs'] = self.object.progress_logs.all()
        context['attachments'] = self.object.attachments.all()
        context['comments'] = self.object.comments.select_related('author').all()
        context['logs'] = self.object.logs.select_related('operator').all()
        context['comment_form'] = RequirementCommentForm()
        context['progress_form'] = RequirementProgressForm()
        return context


class RDRequirementCreateView(LoginRequiredMixin, CreateView):
    """创建研发需求"""
    model = RDRequirement
    template_name = 'rd_requirement/requirement_form.html'
    form_class = RDRequirementForm
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['assignee'].queryset = User.objects.filter(role__in=['rd', 'rd_leader'])
        form.fields['related_customer'].queryset = Customer.objects.all().order_by('customer_code')
        form.fields['related_fae_task'].queryset = FAETask.objects.all().order_by('-created_at')
        
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
        
        # 创建操作日志
        status_display = dict(RDRequirement.STATUS_CHOICES).get(self.object.status, self.object.status)
        RequirementLog.objects.create(
            requirement=self.object,
            operator=self.request.user,
            action=f'创建需求：{status_display}',
            new_status=self.object.status
        )
        
        messages.success(self.request, '研发需求创建成功')
        return response
    
    def get_success_url(self):
        return reverse_lazy('rd_requirement:requirement_detail', kwargs={'pk': self.object.pk})


class RDRequirementUpdateView(LoginRequiredMixin, UpdateView):
    """更新研发需求"""
    model = RDRequirement
    template_name = 'rd_requirement/requirement_form.html'
    form_class = RDRequirementForm
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['assignee'].queryset = User.objects.filter(role__in=['rd', 'rd_leader'])
        form.fields['related_customer'].queryset = Customer.objects.all().order_by('customer_code')
        form.fields['related_fae_task'].queryset = FAETask.objects.all().order_by('-created_at')
        return form
    
    def form_valid(self, form):
        old_instance = RDRequirement.objects.get(pk=self.object.pk)
        old_status = old_instance.status
        response = super().form_valid(form)
        
        # 记录操作日志
        changed_fields = []
        detail_changes = []
        
        # 比较所有字段
        field_comparisons = [
            ('title', '标题', None),
            ('requirement_type', '需求类型', RDRequirement.REQUIREMENT_TYPE_CHOICES),
            ('priority', '优先级', RDRequirement.PRIORITY_CHOICES),
            ('status', '状态', RDRequirement.STATUS_CHOICES),
            ('description', '需求描述', None),
            ('report_date', '汇报日期', None),
            ('start_date', '开始时间', None),
            ('end_date', '截止时间', None),
            ('delay_risk', '延期风险', RDRequirement.DELAY_RISK_CHOICES),
            ('jira_number', 'Jira编号', None),
        ]
        
        for field_name, field_label, choices in field_comparisons:
            old_value = getattr(old_instance, field_name)
            new_value = getattr(self.object, field_name)
            
            # 特殊处理富文本字段：去除HTML标签后比较
            if field_name in ['description', 'delay_reason']:
                old_text = re.sub(r'<[^>]+>', '', str(old_value or '')).strip()
                new_text = re.sub(r'<[^>]+>', '', str(new_value or '')).strip()
                # 如果去除HTML后都是空，视为相同
                if not old_text and not new_text:
                    continue
                changed = old_text != new_text
            else:
                changed = old_value != new_value
            
            if changed:
                changed_fields.append(field_label)
                
                # 处理空值
                old_display = old_value
                new_display = new_value
                
                # 如果有选项映射
                if choices:
                    choices_dict = dict(choices)
                    old_display = choices_dict.get(old_value, old_value)
                    new_display = choices_dict.get(new_value, new_value)
                
                # 特殊处理富文本字段
                if field_name in ['description', 'delay_reason']:
                    old_text = re.sub(r'<[^>]+>', '', str(old_value or '')).strip()
                    new_text = re.sub(r'<[^>]+>', '', str(new_value or '')).strip()
                    old_display = (old_text[:30] + '...') if old_text else '无'
                    new_display = (new_text[:30] + '...') if new_text else '无'
                elif field_name in ['start_date', 'end_date', 'report_date']:
                    old_display = old_value or '未设置'
                    new_display = new_value or '未设置'
                else:
                    old_display = old_value or '无'
                    new_display = new_value or '无'
                
                detail_changes.append(f"{field_label}：{old_display} → {new_display}")
        
        # ForeignKey 字段单独处理
        if old_instance.assignee != self.object.assignee:
            changed_fields.append('负责人')
            old_display = old_instance.assignee.get_full_name() or old_instance.assignee.username if old_instance.assignee else '无'
            new_display = self.object.assignee.get_full_name() or self.object.assignee.username if self.object.assignee else '无'
            detail_changes.append(f"负责人：{old_display} → {new_display}")
        
        if old_instance.related_customer != self.object.related_customer:
            changed_fields.append('关联客户')
            old_display = old_instance.related_customer.customer_code if old_instance.related_customer else '无'
            new_display = self.object.related_customer.customer_code if self.object.related_customer else '无'
            detail_changes.append(f"关联客户：{old_display} → {new_display}")
        
        if old_instance.related_fae_task != self.object.related_fae_task:
            changed_fields.append('关联FAE任务')
            old_display = old_instance.related_fae_task.task_number if old_instance.related_fae_task else '无'
            new_display = self.object.related_fae_task.task_number if self.object.related_fae_task else '无'
            detail_changes.append(f"关联FAE任务：{old_display} → {new_display}")
        
        if changed_fields:
            action = f"更新需求（{', '.join(changed_fields)}）"
            comment = '；'.join(detail_changes)
            RequirementLog.objects.create(
                requirement=self.object,
                operator=self.request.user,
                action=action,
                comment=comment,
                old_status=old_status if old_status != self.object.status else '',
                new_status=self.object.status if old_status != self.object.status else ''
            )
            
            # 记录项目时间线（仅状态变更时）
            if self.object.project and old_status != self.object.status:
                from project.signals import record_project_activity
                status_dict = dict(RDRequirement.STATUS_CHOICES)
                old_status_display = status_dict.get(old_status, old_status)
                new_status_display = status_dict.get(self.object.status, self.object.status)
                record_project_activity(
                    project=self.object.project,
                    actor=self.request.user,
                    action='status_change',
                    instance=self.object,
                    description=f"状态：{old_status_display} → {new_status_display}"
                )
        
        messages.success(self.request, '研发需求更新成功')
        return response
    
    def get_success_url(self):
        return reverse_lazy('rd_requirement:requirement_detail', kwargs={'pk': self.object.pk})


class RequirementProgressCreateView(LoginRequiredMixin, View):
    """添加进展记录"""
    def post(self, request, pk):
        requirement = get_object_or_404(RDRequirement, pk=pk)
        form = RequirementProgressForm(request.POST)
        
        # 手动验证内容是否为空
        content = request.POST.get('content', '').strip()
        if not content:
            messages.error(request, '进展内容不能为空')
            return redirect('rd_requirement:requirement_detail', pk=pk)
        
        if form.is_valid():
            progress = form.save(commit=False)
            progress.requirement = requirement
            progress.reported_by = request.user
            progress.progress_percent = request.POST.get('progress_percent', 0)
            progress.save()
            messages.success(request, '进展记录添加成功')
        else:
            messages.error(request, f'表单验证失败: {form.errors}')
        
        return redirect('rd_requirement:requirement_detail', pk=pk)


class RequirementAttachmentCreateView(LoginRequiredMixin, View):
    """上传附件"""
    def post(self, request, pk):
        requirement = get_object_or_404(RDRequirement, pk=pk)
        file = request.FILES.get('file')
        description = request.POST.get('description', '')
        
        if file:
            RequirementAttachment.objects.create(
                requirement=requirement,
                file=file,
                description=description,
                uploaded_by=request.user
            )
            messages.success(request, '附件上传成功')
        else:
            messages.error(request, '请选择要上传的文件')
        
        return redirect('rd_requirement:requirement_detail', pk=pk)


class RequirementCommentCreateView(LoginRequiredMixin, CreateView):
    """添加需求评论"""
    model = RequirementComment
    form_class = RequirementCommentForm
    
    def form_valid(self, form):
        requirement = get_object_or_404(RDRequirement, pk=self.kwargs['pk'])
        form.instance.requirement = requirement
        form.instance.author = self.request.user
        messages.success(self.request, '评论添加成功')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('rd_requirement:requirement_detail', kwargs={'pk': self.kwargs['pk']})


class RequirementCommentDeleteView(LoginRequiredMixin, View):
    """删除需求评论（仅评论作者可删除）"""
    def post(self, request, pk, comment_pk):
        comment = get_object_or_404(RequirementComment, pk=comment_pk)
        
        # 验证是否为评论作者
        if comment.author != request.user:
            messages.error(request, '您只能删除自己发布的评论')
            return redirect('rd_requirement:requirement_detail', pk=pk)
        
        comment.delete()
        messages.success(request, '评论已删除')
        return redirect('rd_requirement:requirement_detail', pk=pk)
