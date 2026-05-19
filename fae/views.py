"""
FAE 任务管理视图
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View, ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.views import LoginView as BaseLoginView, LogoutView as BaseLogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.utils import timezone
from django.db import models
from django.db.models import Q, Count
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
import re
from .models import User, Customer, FAETask, FAETaskLog, FAETaskComment, Notification, LogAnalyzerKeyword
from .forms import FAETaskCommentForm, FAETaskForm
from testing.models import TestItem, TestItemLog, TestComment
from abnormal.models import AbnormalSample, AbnormalLog, TestRecordEntry
from rd_requirement.models import RDRequirement, RequirementLog
from solution.models import Solution
from datetime import datetime, timedelta


def create_task_notifications(task, sender, notification_type, title, message=''):
    """
    创建任务相关的通知
    通知对象：创建人、负责人、FAE主管（不包括发送者自己）
    """
    # 获取所有需要通知的用户
    recipients = set()
    
    # 添加创建人
    if task.created_by and task.created_by != sender:
        recipients.add(task.created_by)
    
    # 添加负责人
    if task.assignee and task.assignee != sender:
        recipients.add(task.assignee)
    
    # 添加所有FAE主管
    leaders = User.objects.filter(role='fae_leader')
    for leader in leaders:
        if leader != sender:
            recipients.add(leader)
    
    # 为每个接收者创建通知
    for recipient in recipients:
        Notification.objects.create(
            recipient=recipient,
            sender=sender,
            task=task,
            notification_type=notification_type,
            title=title,
            message=message
        )


class DashboardView(LoginRequiredMixin, View):
    """动态个性化首页 - 根据用户角色展示不同的待处理项和通知"""
    template_name = 'dashboard.html'
    
    def get(self, request):
        user = request.user
        now = timezone.now()

        # 获取截至时间参数，默认7天前
        since_str = request.GET.get('since', '')
        if since_str:
            try:
                since_date = datetime.strptime(since_str, '%Y-%m-%d').date()
                since = datetime.combine(since_date, datetime.min.time())
            except ValueError:
                since = now - timedelta(days=7)
        else:
            since = now - timedelta(days=7)

        context = {
            'user': user,
            'now': now,
            'since_date': since.date(),
            'since_str': since.strftime('%Y-%m-%d'),
        }

        def _annotate_yield(tests):
            for t in tests:
                t.yield_rate = round(t.passed_samples / t.total_samples * 100, 1) if t.status == 'completed' and t.total_samples > 0 else None
            return tests

        # FAE 任务
        fae_qs = FAETask.objects.select_related('customer', 'assignee').filter(created_at__gte=since).order_by('-created_at')
        context['fae_tasks'] = fae_qs[:50]

        # 测试跟踪
        test_qs = TestItem.objects.select_related('customer', 'tracker', 'solution').prefetch_related('fae_tasks').filter(created_at__gte=since).order_by('-created_at')
        context['test_items'] = _annotate_yield(list(test_qs[:50]))

        # 异常样品
        abnormal_qs = AbnormalSample.objects.select_related('customer', 'assignee').filter(created_at__gte=since).order_by('-created_at')
        context['abnormal_samples'] = abnormal_qs[:50]

        context['total_count'] = len(context['fae_tasks']) + len(context['test_items']) + len(context['abnormal_samples'])

        return render(request, self.template_name, context)
    
    def _get_fae_dashboard(self, user):
        """FAE工程师和主管的首页数据"""
        data = {}
        
        # 我的待处理任务
        if user.role == 'fae_leader':
            # 主管看到所有待审核的任务
            data['pending_review_tasks'] = FAETask.objects.filter(
                status='pending_review'
            ).select_related('customer', 'assignee').order_by('-created_at')[:10]
            
            # 主管看到所有进行中的任务
            data['my_tasks'] = FAETask.objects.filter(
                status__in=['not_started', 'in_progress']
            ).select_related('customer', 'assignee').order_by('-created_at')[:10]
        else:
            # 普通FAE只看自己的任务
            data['my_tasks'] = FAETask.objects.filter(
                assignee=user,
                status__in=['not_started', 'in_progress']
            ).select_related('customer').order_by('-created_at')[:10]
            
            # 等待我处理的任务（状态变更）
            data['pending_action_tasks'] = FAETask.objects.filter(
                assignee=user,
                status='not_started'
            ).select_related('customer').order_by('-created_at')[:5]
        
        # 我的测试跟踪
        data['my_tests'] = TestItem.objects.filter(
            tracker=user,
            status__in=['not_started', 'in_progress']
        ).select_related('customer').order_by('-created_at')[:10]
        
        # 我的异常样品
        data['my_abnormals'] = AbnormalSample.objects.filter(
            Q(assignee=user) | Q(created_by=user),
            status__in=['pending_analysis', 'retesting']
        ).select_related('customer').order_by('-created_at')[:10]
        
        # 待处理统计
        data['stats'] = {
            'pending_tasks': FAETask.objects.filter(
                assignee=user if user.role == 'fae' else None,
                status__in=['not_started', 'in_progress']
            ).count() if user.role == 'fae' else FAETask.objects.filter(
                status__in=['not_started', 'in_progress']
            ).count(),
            'pending_review': FAETask.objects.filter(status='pending_review').count(),
            'pending_tests': TestItem.objects.filter(tracker=user, status='in_progress').count(),
            'pending_abnormals': AbnormalSample.objects.filter(
                Q(assignee=user) | Q(created_by=user),
                status='pending_analysis'
            ).count(),
        }
        
        # 与我相关的研发需求
        data['related_requirements'] = RDRequirement.objects.filter(
            Q(related_fae_task__assignee=user) | Q(created_by=user),
            status__in=['rd_confirming', 'customer_confirming', 'in_progress']
        ).select_related('assignee').order_by('-created_at')[:5]
        
        return data
    
    def _get_rd_dashboard(self, user):
        """研发工程师和主管的首页数据"""
        data = {}
        
        # 我的研发需求
        if user.role == 'rd_leader':
            # 主管看到所有需要确认的需求
            data['pending_confirm_requirements'] = RDRequirement.objects.filter(
                status='rd_confirming'
            ).select_related('assignee', 'created_by').order_by('-created_at')[:10]
            
            # 所有进行中需求
            data['my_requirements'] = RDRequirement.objects.filter(
                status__in=['rd_confirming', 'customer_confirming', 'in_progress', 'customer_verifying']
            ).select_related('assignee').order_by('-created_at')[:10]
        else:
            # 普通研发只看自己的需求
            data['my_requirements'] = RDRequirement.objects.filter(
                assignee=user,
                status__in=['rd_confirming', 'customer_confirming', 'in_progress', 'customer_verifying']
            ).select_related('created_by').order_by('-created_at')[:10]
        
        # 待处理统计
        data['stats'] = {
            'pending_requirements': RDRequirement.objects.filter(
                assignee=user if user.role == 'rd' else None,
                status__in=['rd_confirming', 'in_progress']
            ).count() if user.role == 'rd' else RDRequirement.objects.filter(
                status__in=['rd_confirming', 'in_progress']
            ).count(),
            'pending_confirm': RDRequirement.objects.filter(status='rd_confirming').count(),
            'high_priority': RDRequirement.objects.filter(
                priority='p0',
                status__in=['rd_confirming', 'in_progress']
            ).count(),
            'customer_verify': RDRequirement.objects.filter(status='customer_verifying').count(),
        }
        
        # 关联的FAE任务（研发需要了解的）
        data['related_tasks'] = FAETask.objects.filter(
            rd_requirements__assignee=user,
            status__in=['in_progress', 'pending_review']
        ).select_related('customer', 'assignee').distinct()[:5]
        
        return data
    
    def _get_warehouse_dashboard(self, user):
        """仓库管理员首页数据"""
        data = {}
        
        # 仓库管理相关的统计
        data['stats'] = {
            'total_solutions': Solution.objects.filter(status='release').count(),
            'recent_solutions': Solution.objects.filter(
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count(),
        }
        
        return data
    
    def _get_admin_dashboard(self, user):
        """管理员首页数据 - 查看所有"""
        data = {}
        
        data['stats'] = {
            'total_tasks': FAETask.objects.count(),
            'active_tasks': FAETask.objects.filter(status__in=['not_started', 'in_progress']).count(),
            'total_tests': TestItem.objects.count(),
            'active_abnormals': AbnormalSample.objects.filter(status__in=['pending_analysis', 'retesting']).count(),
            'total_requirements': RDRequirement.objects.count(),
            'pending_reviews': FAETask.objects.filter(status='pending_review').count(),
        }
        
        # 系统概览
        data['overview'] = {
            'recent_tasks': FAETask.objects.select_related('customer', 'assignee').order_by('-created_at')[:5],
            'recent_tests': TestItem.objects.select_related('customer', 'tracker').order_by('-created_at')[:5],
            'recent_abnormals': AbnormalSample.objects.select_related('customer').order_by('-created_at')[:5],
            'recent_requirements': RDRequirement.objects.select_related('assignee').order_by('-created_at')[:5],
        }
        
        return data
    
    def _get_recent_activities(self, user):
        """获取与用户相关的最近动态"""
        activities = []
        
        # FAE任务相关动态
        task_logs = FAETaskLog.objects.filter(
            Q(task__assignee=user) | 
            Q(task__created_by=user) |
            Q(operator=user)
        ).select_related('task', 'operator').order_by('-created_at')[:5]
        
        for log in task_logs:
            activities.append({
                'type': 'task',
                'icon': 'fa-tasks',
                'color': 'text-blue-400',
                'bg': 'bg-blue-500/10',
                'title': f"任务 {log.task.task_number}",
                'action': log.action,
                'operator': log.operator.get_full_name() or log.operator.username,
                'time': log.created_at,
                'link': f"/fae/tasks/{log.task.pk}/"
            })
        
        # 测试相关动态
        test_logs = TestItemLog.objects.filter(
            Q(test_item__tracker=user) |
            Q(operator=user)
        ).select_related('test_item', 'operator').order_by('-created_at')[:5]
        
        for log in test_logs:
            activities.append({
                'type': 'test',
                'icon': 'fa-vial',
                'color': 'text-cyan-400',
                'bg': 'bg-cyan-500/10',
                'title': f"测试 {log.test_item.test_number}",
                'action': log.action,
                'operator': log.operator.get_full_name() or log.operator.username,
                'time': log.created_at,
                'link': f"/testing/tests/{log.test_item.pk}/"
            })
        
        # 异常样品相关动态
        abnormal_logs = AbnormalLog.objects.filter(
            Q(abnormal_sample__assignee=user) |
            Q(abnormal_sample__created_by=user) |
            Q(operator=user)
        ).select_related('abnormal_sample', 'operator').order_by('-created_at')[:5]
        
        for log in abnormal_logs:
            activities.append({
                'type': 'abnormal',
                'icon': 'fa-exclamation-triangle',
                'color': 'text-red-400',
                'bg': 'bg-red-500/10',
                'title': f"异常 {log.abnormal_sample.sample_number}",
                'action': log.action,
                'operator': log.operator.get_full_name() or log.operator.username,
                'time': log.created_at,
                'link': f"/abnormal/{log.abnormal_sample.pk}/"
            })
        
        # 研发需求相关动态
        req_logs = RequirementLog.objects.filter(
            Q(requirement__assignee=user) |
            Q(requirement__created_by=user) |
            Q(operator=user)
        ).select_related('requirement', 'operator').order_by('-created_at')[:5]
        
        for log in req_logs:
            activities.append({
                'type': 'requirement',
                'icon': 'fa-flask',
                'color': 'text-green-400',
                'bg': 'bg-green-500/10',
                'title': f"需求 {log.requirement.requirement_number}",
                'action': log.action,
                'operator': log.operator.get_full_name() or log.operator.username,
                'time': log.created_at,
                'link': f"/rd_requirement/requirements/{log.requirement.pk}/"
            })
        
        # 按时间排序并取前10条
        activities.sort(key=lambda x: x['time'], reverse=True)
        return activities[:10]
    
    def _get_unread_notifications(self, user):
        """获取用户的未读通知（待处理项）"""
        notifications = []
        
        # 从通知模型获取未读通知
        unread_notifications = Notification.objects.filter(
            recipient=user,
            is_read=False
        ).select_related('sender', 'task').order_by('-created_at')[:10]
        
        for notif in unread_notifications:
            icon_map = {
                'task_updated': 'fa-edit',
                'task_commented': 'fa-comment',
                'task_status_changed': 'fa-exchange-alt',
                'task_reviewed': 'fa-clipboard-check',
            }
            color_map = {
                'task_updated': 'text-blue-400',
                'task_commented': 'text-green-400',
                'task_status_changed': 'text-yellow-400',
                'task_reviewed': 'text-purple-400',
            }
            notifications.append({
                'type': 'notification',
                'icon': icon_map.get(notif.notification_type, 'fa-bell'),
                'color': color_map.get(notif.notification_type, 'text-slate-400'),
                'title': notif.title,
                'content': notif.message[:50] + '...' if len(notif.message) > 50 else notif.message,
                'from_user': notif.sender.get_full_name() or notif.sender.username,
                'time': notif.created_at,
                'link': f"/fae/tasks/{notif.task.pk}/",
                'is_urgent': notif.notification_type == 'task_reviewed',
                'notification_id': notif.pk,
            })
        
        # 新分配给我的任务
        new_tasks = FAETask.objects.filter(
            assignee=user,
            status='not_started',
            created_at__gte=timezone.now() - timedelta(days=7)
        ).select_related('customer', 'created_by')
        
        for task in new_tasks:
            notifications.append({
                'type': 'new_task',
                'icon': 'fa-tasks',
                'color': 'text-blue-400',
                'title': f"新任务分配",
                'content': f"{task.task_number} - {task.customer.customer_code}",
                'from_user': task.created_by.get_full_name() or task.created_by.username,
                'time': task.created_at,
                'link': f"/fae/tasks/{task.pk}/",
                'is_urgent': False
            })
        
        # 需要我审核的任务（主管）
        if user.role == 'fae_leader':
            review_tasks = FAETask.objects.filter(
                status='pending_review',
                created_at__gte=timezone.now() - timedelta(days=7)
            ).select_related('customer', 'assignee')
            
            for task in review_tasks:
                notifications.append({
                    'type': 'pending_review',
                    'icon': 'fa-clipboard-check',
                    'color': 'text-yellow-400',
                    'title': f"待审核任务",
                    'content': f"{task.task_number} - {task.customer.customer_code}",
                    'from_user': task.assignee.get_full_name() or task.assignee.username,
                    'time': task.updated_at,
                    'link': f"/fae/tasks/{task.pk}/",
                    'is_urgent': True
                })
        
        # 需要我确认的研发需求（研发）
        if user.role in ['rd', 'rd_leader']:
            confirm_reqs = RDRequirement.objects.filter(
                Q(assignee=user) if user.role == 'rd' else Q(status='rd_confirming'),
                status='rd_confirming',
                created_at__gte=timezone.now() - timedelta(days=7)
            ).select_related('created_by')
            
            for req in confirm_reqs:
                notifications.append({
                    'type': 'pending_confirm',
                    'icon': 'fa-flask',
                    'color': 'text-purple-400',
                    'title': f"待确认需求",
                    'content': f"{req.requirement_number} - {req.title[:20]}...",
                    'from_user': req.created_by.get_full_name() or req.created_by.username,
                    'time': req.created_at,
                    'link': f"/rd_requirement/requirements/{req.pk}/",
                    'is_urgent': req.priority == 'p0'
                })
        
        # 高优先级异常
        urgent_abnormals = AbnormalSample.objects.filter(
            Q(assignee=user) | Q(created_by=user),
            priority='urgent',
            status__in=['pending_analysis', 'retesting']
        ).select_related('customer')
        
        for abnormal in urgent_abnormals:
            notifications.append({
                'type': 'urgent_abnormal',
                'icon': 'fa-exclamation-circle',
                'color': 'text-red-400',
                'title': f"紧急异常样品",
                'content': f"{abnormal.sample_number} - {abnormal.customer.customer_code}",
                'from_user': '系统',
                'time': abnormal.created_at,
                'link': f"/abnormal/{abnormal.pk}/",
                'is_urgent': True
            })
        
        # 按时间排序
        notifications.sort(key=lambda x: x['time'], reverse=True)
        return notifications[:10]


class LoginView(BaseLoginView):
    """用户登录"""
    template_name = 'login.html'
    redirect_authenticated_user = True


class LogoutView(View):
    """用户登出 - 支持 GET 和 POST"""
    def get(self, request):
        from django.contrib.auth import logout
        logout(request)
        return redirect('login')
    
    def post(self, request):
        from django.contrib.auth import logout
        logout(request)
        return redirect('login')


# ==================== 客户管理 ====================

class CustomerListView(LoginRequiredMixin, ListView):
    """客户列表"""
    model = Customer
    template_name = 'fae/customer_list.html'
    context_object_name = 'customers'
    paginate_by = 20


class CustomerCreateView(LoginRequiredMixin, CreateView):
    """创建客户"""
    model = Customer
    template_name = 'fae/customer_form.html'
    fields = ['customer_code']
    success_url = reverse_lazy('fae:customer_list')
    
    def form_valid(self, form):
        messages.success(self.request, '客户创建成功')
        return super().form_valid(form)


# ==================== FAE 任务管理 ====================

class FAETaskListView(LoginRequiredMixin, ListView):
    """FAE任务列表"""
    model = FAETask
    template_name = 'fae/task_list.html'
    context_object_name = 'tasks'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = FAETask.objects.select_related('customer', 'assignee').order_by('-created_at')
        
        # 状态筛选
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # 搜索
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(task_number__icontains=search) |
                Q(customer__customer_code__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = FAETask.TASK_STATUS_CHOICES
        context['current_status'] = self.request.GET.get('status', '')
        return context


class FAETaskDetailView(LoginRequiredMixin, DetailView):
    """FAE任务详情"""
    model = FAETask
    template_name = 'fae/task_detail.html'
    context_object_name = 'task'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comment_form'] = FAETaskCommentForm()
        context['logs'] = self.object.logs.select_related('operator').all()[:10]
        return context


class FAETaskCreateView(LoginRequiredMixin, CreateView):
    """创建FAE任务"""
    model = FAETask
    form_class = FAETaskForm
    template_name = 'fae/task_form.html'
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
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
        
        # 创建日志
        FAETaskLog.objects.create(
            task=self.object,
            operator=self.request.user,
            action=f"创建任务（{self.object.task_number}）",
            new_status=self.object.status
        )
        
        messages.success(self.request, f'任务 {self.object.task_number} 创建成功')
        return response
    
    def get_success_url(self):
        return reverse_lazy('fae:task_detail', kwargs={'pk': self.object.pk})


class FAETaskUpdateView(LoginRequiredMixin, UpdateView):
    """编辑FAE任务"""
    model = FAETask
    form_class = FAETaskForm
    template_name = 'fae/task_form.html'
    
    # 字段显示名称映射
    FIELD_DISPLAY_NAMES = {
        'assignee': '负责人',
        'customer': '客户',
        'task_type': '任务类型',
        'description': '任务描述',
        'test_items': '关联测试项',
    }
    
    def form_valid(self, form):
        # 获取编辑前的值
        old_instance = self.get_object()
        old_status = old_instance.status
        
        response = super().form_valid(form)
        
        # 检测变更的字段
        changed_fields = []
        detail_changes = []
        
        # 检测基本字段变更
        for field, label in self.FIELD_DISPLAY_NAMES.items():
            old_value = getattr(old_instance, field)
            new_value = getattr(self.object, field)
            
            if field == 'test_items':
                # ManyToManyField 特殊处理 - 比较ID集合
                old_ids = set(old_value.all().values_list('id', flat=True))
                new_ids = set(new_value.all().values_list('id', flat=True))
                if old_ids != new_ids:
                    changed_fields.append(label)
                    added_count = len(new_ids - old_ids)
                    removed_count = len(old_ids - new_ids)
                    if added_count and removed_count:
                        detail_changes.append(f"{label}: 添加{added_count}个, 移除{removed_count}个")
                    elif added_count:
                        detail_changes.append(f"{label}: 添加{added_count}个")
                    elif removed_count:
                        detail_changes.append(f"{label}: 移除{removed_count}个")
                continue
            
            # ForeignKey 和 普通字段的比较
            changed = False
            if field in ['assignee', 'customer']:
                # ForeignKey 比较 ID
                old_id = old_value.id if old_value else None
                new_id = new_value.id if new_value else None
                changed = old_id != new_id
            elif field == 'description':
                # 富文本字段，去除空白后比较
                old_clean = old_value.strip() if old_value else ''
                new_clean = new_value.strip() if new_value else ''
                changed = old_clean != new_clean
            else:
                changed = old_value != new_value
            
            if changed:
                changed_fields.append(label)
                # 获取显示值
                if field == 'assignee':
                    old_display = old_value.get_full_name() or old_value.username if old_value else '无'
                    new_display = new_value.get_full_name() or new_value.username if new_value else '无'
                elif field == 'customer':
                    old_display = old_value.customer_code if old_value else '无'
                    new_display = new_value.customer_code if new_value else '无'
                elif field == 'task_type':
                    old_display = dict(FAETask.TASK_TYPE_CHOICES).get(old_value, old_value)
                    new_display = dict(FAETask.TASK_TYPE_CHOICES).get(new_value, new_value)
                elif field == 'description':
                    # 去除HTML标签后取前50字符作为摘要
                    import re
                    old_text = re.sub(r'<[^>]+>', '', old_value).strip() if old_value else ''
                    new_text = re.sub(r'<[^>]+>', '', new_value).strip() if new_value else ''
                    old_display = old_text[:50] + '...' if len(old_text) > 50 else (old_text or '无')
                    new_display = new_text[:50] + '...' if len(new_text) > 50 else (new_text or '无')
                else:
                    old_display = str(old_value) if old_value is not None else ''
                    new_display = str(new_value) if new_value is not None else ''
                detail_changes.append(f"{label}: {old_display} → {new_display}")
        
        # 构建操作描述
        if changed_fields:
            action = f"更新任务（{', '.join(changed_fields)}）"
            comment = '; '.join(detail_changes)
        else:
            action = '编辑了任务'
            comment = ''
        
        # 创建日志
        FAETaskLog.objects.create(
            task=self.object,
            operator=self.request.user,
            action=action,
            comment=comment,
            old_status=old_status,
            new_status=self.object.status
        )
        
        # 创建通知（有变更时才通知）
        if changed_fields:
            create_task_notifications(
                task=self.object,
                sender=self.request.user,
                notification_type='task_updated',
                title=f"任务 {self.object.task_number} 已更新",
                message=f"{self.request.user.get_full_name() or self.request.user.username} 更新了任务：{action}\n{comment}"
            )
        
        # 记录项目时间线（仅状态变更时）
        if self.object.project and old_status != self.object.status:
            from project.signals import record_project_activity
            status_dict = dict(FAETask.STATUS_CHOICES)
            old_status_display = status_dict.get(old_status, old_status)
            new_status_display = status_dict.get(self.object.status, self.object.status)
            record_project_activity(
                project=self.object.project,
                actor=self.request.user,
                action='status_change',
                instance=self.object,
                description=f"状态：{old_status_display} → {new_status_display}"
            )
        
        messages.success(self.request, f'任务 {self.object.task_number} 更新成功')
        return response
    
    def get_success_url(self):
        return reverse_lazy('fae:task_detail', kwargs={'pk': self.object.pk})


class NotificationMarkReadView(LoginRequiredMixin, View):
    """标记单个通知已读"""
    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({'status': 'success'})


class NotificationMarkTaskReadView(LoginRequiredMixin, View):
    """标记指定任务的所有通知已读"""
    def post(self, request, pk):
        # 只标记与该任务相关的通知
        Notification.objects.filter(
            recipient=request.user,
            task_id=pk,
            is_read=False
        ).update(is_read=True)
        return JsonResponse({'status': 'success'})


class FAETaskDeleteView(LoginRequiredMixin, DeleteView):
    """删除FAE任务"""
    model = FAETask
    template_name = 'fae/task_confirm_delete.html'
    success_url = reverse_lazy('fae:task_list')
    
    def delete(self, request, *args, **kwargs):
        task = self.get_object()
        messages.success(request, f'任务 {task.task_number} 已删除')
        return super().delete(request, *args, **kwargs)


class FAETaskReviewView(LoginRequiredMixin, View):
    """审核FAE任务"""
    def post(self, request, pk):
        task = get_object_or_404(FAETask, pk=pk)
        review_result = request.POST.get('review_result')
        review_comment = request.POST.get('review_comment', '')
        
        if review_result in ['passed', 'rejected']:
            old_status = task.status
            
            if review_result == 'passed':
                task.status = 'completed'
                action = '审核通过'
            else:
                task.status = 'in_progress'
                action = '审核不通过'
            
            task.review_result = review_result
            task.review_comment = review_comment
            task.reviewed_by = request.user
            task.reviewed_at = timezone.now()
            task.save()
            
            # 创建日志
            FAETaskLog.objects.create(
                task=task,
                operator=request.user,
                action=f"审核任务（{action}）",
                comment=review_comment if review_comment else f"审核结果: {action}",
                old_status=old_status,
                new_status=task.status
            )
            
            # 创建通知
            create_task_notifications(
                task=task,
                sender=request.user,
                notification_type='task_reviewed',
                title=f"任务 {task.task_number} 审核完成",
                message=f"{request.user.get_full_name() or request.user.username} 审核了任务：{action}\n{review_comment if review_comment else ''}"
            )
            
            # 记录项目时间线
            if task.project:
                from project.signals import record_project_activity
                old_status_display = dict(FAETask.TASK_STATUS_CHOICES).get(old_status, old_status)
                new_status_display = task.get_status_display()
                desc = f"审核：{action} | 状态：{old_status_display} → {new_status_display}"
                if review_comment:
                    desc += f" | 审核意见：{review_comment}"
                record_project_activity(
                    project=task.project,
                    actor=request.user,
                    action='status_change',
                    instance=task,
                    description=desc
                )
            
            messages.success(request, f'任务 {task.task_number} 审核完成')
        
        return redirect('fae:task_detail', pk=pk)


class FAETaskChangeStatusView(LoginRequiredMixin, View):
    """变更任务状态"""
    def get(self, request, pk):
        """显示状态变更表单（用于待审核状态需要输入任务结论）"""
        task = get_object_or_404(FAETask, pk=pk)
        new_status = request.GET.get('status')
        
        if new_status == 'pending_review':
            return render(request, 'fae/task_change_status.html', {
                'task': task,
                'new_status': new_status,
                'new_status_display': dict(FAETask.TASK_STATUS_CHOICES).get(new_status, new_status),
            })
        
        return redirect('fae:task_detail', pk=pk)
    
    def post(self, request, pk):
        task = get_object_or_404(FAETask, pk=pk)
        new_status = request.POST.get('status')
        
        if new_status in dict(FAETask.TASK_STATUS_CHOICES):
            old_status = task.status
            
            # 如果变为待审核状态，需要保存任务结论
            if new_status == 'pending_review':
                result = request.POST.get('result', '').strip()
                if not result:
                    messages.error(request, '提交审核时必须填写任务结论')
                    return render(request, 'fae/task_change_status.html', {
                        'task': task,
                        'new_status': new_status,
                        'new_status_display': dict(FAETask.TASK_STATUS_CHOICES).get(new_status, new_status),
                    })
                task.result = result
            
            task.status = new_status
            task.save()
            
            # 创建日志
            old_status_display = dict(FAETask.TASK_STATUS_CHOICES).get(old_status, old_status)
            new_status_display = dict(FAETask.TASK_STATUS_CHOICES).get(new_status, new_status)
            
            if new_status == 'pending_review':
                comment = f"状态: {old_status_display} → {new_status_display}，已填写任务结论"
            else:
                comment = f"状态: {old_status_display} → {new_status_display}"
            
            FAETaskLog.objects.create(
                task=task,
                operator=request.user,
                action="更新任务（状态）",
                comment=comment,
                old_status=old_status,
                new_status=new_status
            )
            
            # 创建通知
            create_task_notifications(
                task=task,
                sender=request.user,
                notification_type='task_status_changed',
                title=f"任务 {task.task_number} 状态已变更",
                message=f"{request.user.get_full_name() or request.user.username} 将任务状态从 {old_status_display} 变更为 {new_status_display}"
            )
            
            # 记录项目时间线
            if task.project:
                from project.signals import record_project_activity
                record_project_activity(
                    project=task.project,
                    actor=request.user,
                    action='status_change',
                    instance=task,
                    description=f"状态：{old_status_display} → {new_status_display}"
                )
            
            messages.success(request, f'任务状态已更新为 {task.get_status_display()}')
        
        return redirect('fae:task_detail', pk=pk)


class FAETaskCommentCreateView(LoginRequiredMixin, CreateView):
    """添加任务评论"""
    model = FAETaskComment
    form_class = FAETaskCommentForm
    
    def form_valid(self, form):
        task = get_object_or_404(FAETask, pk=self.kwargs['pk'])
        form.instance.task = task
        form.instance.author = self.request.user
        
        response = super().form_valid(form)
        
        # 创建通知
        create_task_notifications(
            task=task,
            sender=self.request.user,
            notification_type='task_commented',
            title=f"任务 {task.task_number} 有新评论",
            message=f"{self.request.user.get_full_name() or self.request.user.username} 添加了评论"
        )
        
        messages.success(self.request, '评论添加成功')
        return response
    
    def get_success_url(self):
        return reverse_lazy('fae:task_detail', kwargs={'pk': self.kwargs['pk']})


class FAETaskCommentDeleteView(LoginRequiredMixin, View):
    """删除任务评论（仅评论作者可删除）"""
    def post(self, request, pk):
        comment = get_object_or_404(FAETaskComment, pk=pk)
        task_pk = comment.task.pk
        
        if comment.author != request.user:
            messages.error(request, '您只能删除自己发布的评论')
            return redirect('fae:task_detail', pk=task_pk)
        
        comment.delete()
        messages.success(request, '评论已删除')
        return redirect('fae:task_detail', pk=task_pk)



class DailyReportView(LoginRequiredMixin, View):
    """FAE 日报生成 - 一键汇总当日业务数据"""
    template_name = 'fae/daily_report.html'

    def get(self, request):
        # 获取日期参数，默认今天
        date_str = request.GET.get('date', '').strip()
        if date_str:
            try:
                report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                report_date = timezone.now().date()
        else:
            report_date = timezone.now().date()

        # 日期范围（naive datetime，兼容 USE_TZ=False + MySQL）
        start_dt = datetime.combine(report_date, datetime.min.time())
        end_dt = datetime.combine(report_date, datetime.max.time())

        # 1. 当天新建的 FAE 任务
        new_tasks = FAETask.objects.select_related('customer', 'assignee', 'created_by').filter(
            created_at__gte=start_dt, created_at__lte=end_dt
        ).order_by('-created_at')

        # 2. 当天状态发生变更的 FAE 任务（通过日志）
        task_logs = FAETaskLog.objects.select_related('task', 'operator').filter(
            created_at__gte=start_dt, created_at__lte=end_dt
        ).exclude(old_status='').order_by('-created_at')

        # 3. 当天新建的测试项
        new_tests = TestItem.objects.select_related('customer', 'tracker', 'project').filter(
            created_at__gte=start_dt, created_at__lte=end_dt
        ).order_by('-created_at')

        # 4. 当天新建的异常样品
        new_abnormals = AbnormalSample.objects.select_related('customer', 'assignee', 'created_by').filter(
            created_at__gte=start_dt, created_at__lte=end_dt
        ).order_by('-created_at')

        # 5. 当天测试项日志
        test_logs = TestItemLog.objects.select_related('test_item', 'operator').filter(
            created_at__gte=start_dt, created_at__lte=end_dt
        ).order_by('-created_at')

        # 6. 当天异常样品日志
        abnormal_logs = AbnormalLog.objects.select_related('abnormal_sample', 'operator').filter(
            created_at__gte=start_dt, created_at__lte=end_dt
        ).order_by('-created_at')

        context = {
            'report_date': report_date,
            'prev_date': report_date - timedelta(days=1),
            'next_date': report_date + timedelta(days=1),
            'new_tasks': new_tasks,
            'task_logs': task_logs,
            'new_tests': new_tests,
            'new_abnormals': new_abnormals,
            'test_logs': test_logs,
            'abnormal_logs': abnormal_logs,
            'stats': {
                'new_tasks': new_tasks.count(),
                'status_changes': task_logs.count(),
                'new_tests': new_tests.count(),
                'new_abnormals': new_abnormals.count(),
            }
        }
        return render(request, self.template_name, context)


class UserSettingsView(LoginRequiredMixin, View):
    """用户设置视图 - 修改密码和头像"""
    template_name = 'fae/user_settings.html'
    
    def get(self, request):
        return render(request, self.template_name)
    
    def post(self, request):
        user = request.user
        action = request.POST.get('action')
        
        if action == 'change_password':
            old_password = request.POST.get('old_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            # 验证旧密码
            if not user.check_password(old_password):
                messages.error(request, '当前密码不正确')
                return redirect('fae:user_settings')
            
            # 验证新密码
            if new_password != confirm_password:
                messages.error(request, '两次输入的新密码不一致')
                return redirect('fae:user_settings')
            
            if len(new_password) < 6:
                messages.error(request, '新密码长度不能少于6位')
                return redirect('fae:user_settings')
            
            # 修改密码
            user.set_password(new_password)
            user.save()
            messages.success(request, '密码修改成功，请使用新密码重新登录')
            return redirect('login')
        
        elif action == 'change_avatar':
            avatar = request.FILES.get('avatar')
            if avatar:
                # 删除旧头像
                if user.avatar:
                    user.avatar.delete(save=False)
                user.avatar = avatar
                user.save()
                messages.success(request, '头像更新成功')
            else:
                messages.error(request, '请选择要上传的头像')
            return redirect('fae:user_settings')
        

        
        return redirect('fae:user_settings')


# ==================== 日志分析工具 API ====================

@login_required
def api_test_items(request):
    """获取测试项列表（用于日志分析工具关联）"""
    target_id = request.GET.get('id', '').strip()
    if target_id:
        queryset = TestItem.objects.select_related('project').filter(pk=int(target_id))
    else:
        q = request.GET.get('q', '').strip()
        queryset = TestItem.objects.select_related('project').order_by('-created_at')[:100]
        if q:
            queryset = TestItem.objects.select_related('project').filter(
                Q(test_number__icontains=q) | Q(project__name__icontains=q)
            ).order_by('-created_at')[:100]
    data = [{
        'id': t.id,
        'test_number': t.test_number,
        'project': t.project.name if t.project else '-',
        'status': t.get_status_display(),
    } for t in queryset]
    return JsonResponse({'items': data})


@login_required
def api_abnormal_samples(request):
    """获取异常样品列表（用于日志分析工具关联）"""
    target_id = request.GET.get('id', '').strip()
    if target_id:
        queryset = AbnormalSample.objects.select_related('customer').filter(pk=int(target_id))
    else:
        q = request.GET.get('q', '').strip()
        queryset = AbnormalSample.objects.select_related('customer').order_by('-created_at')[:100]
        if q:
            queryset = AbnormalSample.objects.select_related('customer').filter(
                Q(sample_number__icontains=q) | Q(customer__customer_code__icontains=q)
            ).order_by('-created_at')[:100]
    data = [{
        'id': a.id,
        'sample_number': a.sample_number,
        'customer': a.customer.customer_code if a.customer else '-',
        'status': a.get_status_display(),
    } for a in queryset]
    return JsonResponse({'items': data})


@login_required
@require_POST
def api_log_report_submit(request):
    """提交日志分析报告到测试项或异常样品"""
    import json
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': '无效的 JSON 数据'})

    target_type = data.get('target_type')
    target_id = data.get('target_id')
    content = data.get('content', '').strip()

    if not target_type or not target_id:
        return JsonResponse({'success': False, 'error': '请选择目标条目'})
    if not content:
        return JsonResponse({'success': False, 'error': '报告内容不能为空'})

    try:
        if target_type == 'test':
            test = TestItem.objects.get(pk=int(target_id))
            TestComment.objects.create(test=test, content=content, author=request.user)
            return JsonResponse({
                'success': True,
                'message': '报告已添加到测试项 ' + test.test_number,
                'redirect_url': reverse_lazy('testing:test_detail', kwargs={'pk': test.id})
            })
        elif target_type == 'abnormal':
            sample = AbnormalSample.objects.get(pk=int(target_id))
            TestRecordEntry.objects.create(
                abnormal_sample=sample,
                content=content,
                operator=request.user
            )
            return JsonResponse({
                'success': True,
                'message': '报告已添加到异常样品 ' + sample.sample_number,
                'redirect_url': reverse_lazy('abnormal:abnormal_detail', kwargs={'pk': sample.id})
            })
        else:
            return JsonResponse({'success': False, 'error': '未知目标类型'})
    except TestItem.DoesNotExist:
        return JsonResponse({'success': False, 'error': '测试项不存在'})
    except AbnormalSample.DoesNotExist:
        return JsonResponse({'success': False, 'error': '异常样品不存在'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_log_keywords(request):
    """获取日志分析关键词配置"""
    keywords = LogAnalyzerKeyword.objects.filter(is_active=True).order_by('order', 'id')
    data = [{
        'name': kw.name,
        'pattern': kw.pattern,
        'regex': kw.regex,
    } for kw in keywords]
    return JsonResponse({'keywords': data})
