"""问题单视图"""
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.db import transaction, models

from .models import Issue, IssueLog, IssueSolutionRecord, IssueSolutionDetail
from .forms import IssueForm, IssueSolutionRecordForm, IssueSolutionDetailForm


class IssueListView(LoginRequiredMixin, ListView):
    model = Issue
    template_name = 'issue/issue_list.html'
    context_object_name = 'issues'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related('project', 'solution', 'submitter')
        search = self.request.GET.get('search', '')
        status = self.request.GET.get('status', '')
        priority = self.request.GET.get('priority', '')

        if search:
            queryset = queryset.filter(
                models.Q(issue_number__icontains=search) |
                models.Q(project__name__icontains=search) |
                models.Q(solution__name__icontains=search) |
                models.Q(abnormal_description__icontains=search)
            )
        if status:
            queryset = queryset.filter(status=status)
        if priority:
            queryset = queryset.filter(priority=priority)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['priority_filter'] = self.request.GET.get('priority', '')
        context['status_choices'] = Issue.STATUS_CHOICES
        context['priority_choices'] = Issue.PRIORITY_CHOICES
        return context


class IssueDetailView(LoginRequiredMixin, DetailView):
    model = Issue
    template_name = 'issue/issue_detail.html'
    context_object_name = 'issue'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        issue = self.object
        context['solution_records'] = issue.solution_records.prefetch_related('details__test_item', 'details__abnormal_sample', 'details__created_by')
        context['detail_form'] = IssueSolutionDetailForm()
        context['status_choices'] = Issue.STATUS_CHOICES
        context['logs'] = issue.logs.select_related('operator').all()
        return context


class IssueCreateView(LoginRequiredMixin, CreateView):
    model = Issue
    form_class = IssueForm
    template_name = 'issue/issue_form.html'
    success_url = reverse_lazy('issue:issue_list')

    def get_initial(self):
        initial = super().get_initial()
        project_pk = self.request.GET.get('project')
        if project_pk:
            initial['project'] = project_pk
        return initial

    def form_valid(self, form):
        form.instance.submitter = self.request.user
        response = super().form_valid(form)
        IssueLog.objects.create(
            issue=self.object,
            operator=self.request.user,
            action='创建问题单',
            new_status=self.object.status,
        )
        messages.success(self.request, f'问题单 {self.object.issue_number} 创建成功')
        return response


class IssueUpdateView(LoginRequiredMixin, UpdateView):
    model = Issue
    form_class = IssueForm
    template_name = 'issue/issue_form.html'

    def get_success_url(self):
        return reverse('issue:issue_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        old_status = self.object.status
        response = super().form_valid(form)
        new_status = self.object.status
        if old_status != new_status:
            IssueLog.objects.create(
                issue=self.object,
                operator=self.request.user,
                action='更新问题单并变更状态',
                old_status=old_status,
                new_status=new_status,
            )
        else:
            IssueLog.objects.create(
                issue=self.object,
                operator=self.request.user,
                action='更新问题单',
                new_status=new_status,
            )
        messages.success(self.request, f'问题单 {self.object.issue_number} 更新成功')
        return response


class IssueDeleteView(LoginRequiredMixin, DeleteView):
    model = Issue
    template_name = 'issue/issue_confirm_delete.html'
    success_url = reverse_lazy('issue:issue_list')

    def delete(self, request, *args, **kwargs):
        issue = self.get_object()
        messages.success(request, f'问题单 {issue.issue_number} 已删除')
        return super().delete(request, *args, **kwargs)


class IssueChangeStatusView(LoginRequiredMixin, View):
    def post(self, request, pk):
        issue = get_object_or_404(Issue, pk=pk)
        new_status = request.POST.get('status')
        comment = request.POST.get('comment', '')

        if new_status in dict(Issue.STATUS_CHOICES):
            old_status = issue.status
            issue.status = new_status
            if new_status == 'closed':
                issue.closed_at = timezone.now()
            else:
                issue.closed_at = None
            issue.save()

            IssueLog.objects.create(
                issue=issue,
                operator=request.user,
                action='变更状态',
                old_status=old_status,
                new_status=new_status,
                comment=comment,
            )
            messages.success(request, f'问题单状态已更新为：{issue.get_status_display()}')
        else:
            messages.error(request, '无效的状态')

        return redirect('issue:issue_detail', pk=pk)


class IssueSolutionRecordCreateView(LoginRequiredMixin, View):
    """在问题单详情页直接添加一条问题解决记录"""
    def post(self, request, pk):
        issue = get_object_or_404(Issue, pk=pk)
        form = IssueSolutionRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.issue = issue
            record.created_by = request.user
            record.save()
            messages.success(request, '问题解决记录添加成功')
        else:
            messages.error(request, '添加失败，请检查标题')
        return redirect('issue:issue_detail', pk=pk)


class IssueSolutionDetailCreateView(LoginRequiredMixin, View):
    """在某个问题解决记录内添加明细（排查记录/异常样品/根因/解决方案/验证记录）"""
    def post(self, request, pk, record_pk):
        issue = get_object_or_404(Issue, pk=pk)
        solution_record = get_object_or_404(IssueSolutionRecord, pk=record_pk, issue=issue)
        form = IssueSolutionDetailForm(request.POST)
        if form.is_valid():
            detail = form.save(commit=False)
            detail.solution_record = solution_record
            detail.created_by = request.user
            detail.save()
            messages.success(request, f'{detail.get_detail_type_display()}添加成功')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
        return redirect('issue:issue_detail', pk=pk)


class IssueSolutionDetailUpdateView(LoginRequiredMixin, UpdateView):
    """编辑问题解决记录明细"""
    model = IssueSolutionDetail
    form_class = IssueSolutionDetailForm
    template_name = 'issue/issue_solution_detail_form.html'
    pk_url_kwarg = 'detail_pk'

    def get_object(self, queryset=None):
        issue = get_object_or_404(Issue, pk=self.kwargs['pk'])
        solution_record = get_object_or_404(IssueSolutionRecord, pk=self.kwargs['record_pk'], issue=issue)
        return get_object_or_404(IssueSolutionDetail, pk=self.kwargs['detail_pk'], solution_record=solution_record)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['issue'] = get_object_or_404(Issue, pk=self.kwargs['pk'])
        return context

    def get_success_url(self):
        return reverse('issue:issue_detail', kwargs={'pk': self.kwargs['pk']})

    def form_valid(self, form):
        messages.success(self.request, f'{self.object.get_detail_type_display()}更新成功')
        return super().form_valid(form)

    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, error)
        return super().form_invalid(form)


class IssueSolutionRecordDeleteView(LoginRequiredMixin, View):
    """删除整个解决记录及其下所有明细"""
    def post(self, request, pk, record_pk):
        issue = get_object_or_404(Issue, pk=pk)
        record = get_object_or_404(IssueSolutionRecord, pk=record_pk, issue=issue)
        record.delete()
        messages.success(request, '解决记录已删除')
        return redirect('issue:issue_detail', pk=pk)
