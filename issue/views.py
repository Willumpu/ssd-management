"""问题单视图"""
import base64
import datetime
import os
import py7zr
import shutil
import tempfile
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect
from django.template.loader import render_to_string
from django.utils import timezone
from django.db import transaction, models
from django import forms

from .models import Issue, IssueLog, IssueSolutionRecord, IssueSolutionDetail
from .forms import IssueForm, IssueSolutionRecordForm, IssueSolutionDetailForm
from abnormal.forms import AbnormalSampleForm
from fae.models import Customer
from project.models import Project
from solution.models import Solution


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
        project = self.request.GET.get('project', '')

        if search:
            queryset = queryset.filter(
                models.Q(issue_number__icontains=search) |
                models.Q(summary__icontains=search) |
                models.Q(project__name__icontains=search) |
                models.Q(solution__name__icontains=search) |
                models.Q(abnormal_description__icontains=search)
            )
        if status:
            queryset = queryset.filter(status=status)
        if priority:
            queryset = queryset.filter(priority=priority)
        if project:
            queryset = queryset.filter(project_id=project)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['priority_filter'] = self.request.GET.get('priority', '')
        context['status_choices'] = Issue.STATUS_CHOICES
        context['priority_choices'] = Issue.PRIORITY_CHOICES
        context['projects'] = Project.objects.all().order_by('-created_at')
        return context


class IssueDetailView(LoginRequiredMixin, DetailView):
    model = Issue
    template_name = 'issue/issue_detail.html'
    context_object_name = 'issue'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        issue = self.object
        context['solution_records'] = issue.solution_records.prefetch_related('details__test_items', 'details__created_by')
        context['detail_form'] = IssueSolutionDetailForm()
        context['status_choices'] = Issue.STATUS_CHOICES
        context['logs'] = issue.logs.select_related('operator').all()
        context['abnormal_samples'] = issue.abnormal_samples.select_related('customer', 'assignee', 'solution').order_by('-created_at')
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
            form.save_m2m()
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


class IssueAbnormalSampleCreateView(LoginRequiredMixin, View):
    """在问题单内创建异常样品"""
    template_name = 'issue/issue_abnormal_sample_form.html'

    def _prepare_form(self, form, issue):
        """根据问题单自动填充并限制表单选项"""
        form.fields['customer'].queryset = Customer.objects.all().order_by('customer_code')
        form.fields['project'].queryset = Project.objects.filter(pk=issue.project.pk)
        form.fields['solution'].queryset = Solution.objects.filter(pk=issue.solution.pk)

        # 隐藏并固定关联字段
        for field_name in ('project', 'customer', 'solution'):
            form.fields[field_name].widget = forms.HiddenInput()
            form.fields[field_name].required = True

        form.initial['project'] = issue.project.pk
        form.initial['solution'] = issue.solution.pk
        if issue.project.customer:
            form.fields['customer'].queryset = Customer.objects.filter(pk=issue.project.customer.pk)
            form.initial['customer'] = issue.project.customer.pk
        return form

    def get(self, request, pk):
        issue = get_object_or_404(Issue, pk=pk)
        if not issue.project.customer:
            messages.error(request, '该项目未设置客户，无法创建异常样品')
            return redirect('issue:issue_detail', pk=pk)

        form = AbnormalSampleForm()
        form = self._prepare_form(form, issue)
        return render(request, self.template_name, {'issue': issue, 'form': form})

    def post(self, request, pk):
        issue = get_object_or_404(Issue, pk=pk)
        if not issue.project.customer:
            messages.error(request, '该项目未设置客户，无法创建异常样品')
            return redirect('issue:issue_detail', pk=pk)

        form = AbnormalSampleForm(request.POST)
        form = self._prepare_form(form, issue)

        if form.is_valid():
            sample = form.save(commit=False)
            sample.issue = issue
            sample.created_by = request.user
            sample.status = 'pending_analysis'
            sample.save()
            form.save_m2m()

            # 处理日志获取多选
            logs_collected = request.POST.getlist('logs_collected')
            if logs_collected:
                sample.logs_collected = logs_collected
                sample.save(update_fields=['logs_collected'])

            # 记录项目时间线
            if sample.project:
                from project.signals import record_project_activity, build_create_description
                record_project_activity(
                    project=sample.project,
                    actor=request.user,
                    action='create',
                    instance=sample,
                    description=build_create_description(sample, 'abnormal_sample')
                )

            # 创建操作日志
            from abnormal.models import AbnormalLog
            AbnormalLog.objects.create(
                abnormal_sample=sample,
                operator=request.user,
                action='创建异常样品',
                new_status='pending_analysis',
                comment=f'客户: {sample.customer.customer_code}'
            )

            messages.success(request, f'异常样品 {sample.sample_number} 创建成功')
            return redirect('issue:issue_detail', pk=pk)

        return render(request, self.template_name, {'issue': issue, 'form': form})


class IssueReportView(LoginRequiredMixin, View):
    """生成问题单离线 HTML 报告

    - 所有文本/图片日志直接内联到单个 HTML 文件中，双击即可完整查看
    - 同时打包所有原始日志文件为 7z，以 base64 形式嵌入 HTML
    - 页面提供"下载所有日志"按钮，点击可导出原始日志 7z 包
    """
    template_name = 'issue/issue_report.html'
    MAX_EMBED_SIZE = 20 * 1024 * 1024  # 单个文件内联上限 20MB

    TEXT_EXTS = {'.txt', '.log', '.out', '.csv', '.md', '.py', '.sh', '.json', '.xml', '.ini', '.cfg'}
    IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}

    def get(self, request, pk):
        issue = get_object_or_404(
            Issue.objects.select_related('project', 'solution', 'submitter'),
            pk=pk
        )
        solution_records = issue.solution_records.prefetch_related(
            'details__test_items', 'details__created_by'
        )
        abnormal_samples = issue.abnormal_samples.prefetch_related(
            'log_files__uploaded_by'
        )

        report_samples = []
        archive_files = []  # 用于生成下载包 [(safe_name, local_path)]
        used_names = set()

        for sample in abnormal_samples:
            log_files = []
            for lf in sample.log_files.all():
                entry = self._build_log_entry(lf, used_names)
                log_files.append(entry)
                if entry.get('local_path'):
                    archive_files.append((entry['archive_name'], entry['local_path']))
            report_samples.append({'sample': sample, 'log_files': log_files})

        # 生成原始日志 7z 包并 base64 编码
        logs_archive_base64 = ''
        if archive_files:
            logs_archive_base64 = self._build_logs_archive(archive_files)

        context = {
            'issue': issue,
            'solution_records': solution_records,
            'report_samples': report_samples,
            'generated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
            'logs_archive_base64': logs_archive_base64,
            'logs_archive_name': 'issue_logs_{}.7z'.format(issue.issue_number),
        }
        response = render(request, self.template_name, context)
        response['Content-Disposition'] = 'attachment; filename="issue_report_{}.html"'.format(issue.issue_number)
        return response

    def _build_log_entry(self, lf, used_names):
        entry = {
            'filename': lf.filename,
            'log_type': lf.get_log_type_display(),
            'description': lf.description or '',
            'uploaded_at': lf.uploaded_at.strftime('%Y-%m-%d %H:%M'),
            'uploader': lf.uploaded_by.get_full_name() or lf.uploaded_by.username,
            'size': lf.size,
            'size_display': self._format_size(lf.size),
            'is_text': False,
            'is_image': False,
            'content': '',
            'image_data': '',
            'too_large': False,
            'missing': False,
            'archive_name': '',
            'local_path': '',
        }

        lower_name = lf.filename.lower()
        ext = os.path.splitext(lower_name)[1]

        file_path = lf.file.path if lf.file else None
        if file_path and os.path.exists(file_path):
            safe_name = self._unique_name(lf.filename, used_names)
            entry['archive_name'] = safe_name
            entry['local_path'] = file_path

            if lf.size > self.MAX_EMBED_SIZE:
                entry['too_large'] = True
            else:
                try:
                    with open(file_path, 'rb') as f:
                        raw = f.read()
                except Exception:
                    raw = b''

                if ext in self.TEXT_EXTS or (not ext and self._looks_like_text(raw)):
                    try:
                        entry['content'] = raw.decode('utf-8', errors='replace')
                        entry['is_text'] = True
                    except Exception:
                        entry['too_large'] = True
                elif ext in self.IMAGE_EXTS:
                    mime = {
                        '.png': 'image/png',
                        '.jpg': 'image/jpeg',
                        '.jpeg': 'image/jpeg',
                        '.gif': 'image/gif',
                        '.bmp': 'image/bmp',
                        '.webp': 'image/webp',
                    }.get(ext, 'image/png')
                    entry['image_data'] = 'data:{};base64,'.format(mime) + base64.b64encode(raw).decode('ascii')
                    entry['is_image'] = True
                else:
                    # 未知类型：尝试识别为文本，否则视为过大不嵌入
                    try:
                        entry['content'] = raw.decode('utf-8', errors='replace')
                        entry['is_text'] = True
                    except Exception:
                        entry['too_large'] = True
        else:
            entry['missing'] = True

        return entry

    def _build_logs_archive(self, archive_files):
        tmp_dir = tempfile.mkdtemp(prefix='issue_logs_')
        logs_dir = os.path.join(tmp_dir, 'logs')
        os.makedirs(logs_dir, exist_ok=True)

        for safe_name, local_path in archive_files:
            shutil.copy2(local_path, os.path.join(logs_dir, safe_name))

        archive_path = os.path.join(tmp_dir, 'logs.7z')
        with py7zr.SevenZipFile(archive_path, 'w') as archive:
            archive.writeall(logs_dir, 'logs')

        with open(archive_path, 'rb') as f:
            data = f.read()

        shutil.rmtree(tmp_dir, ignore_errors=True)
        return base64.b64encode(data).decode('ascii')

    def _unique_name(self, filename, used_names):
        name = filename or 'unknown'
        if name not in used_names:
            used_names.add(name)
            return name
        base, ext = os.path.splitext(name)
        idx = 1
        while True:
            candidate = '{}_{}{}'.format(base, idx, ext)
            if candidate not in used_names:
                used_names.add(candidate)
                return candidate
            idx += 1

    def _looks_like_text(self, raw):
        if not raw:
            return True
        sample = raw[:4096]
        try:
            sample.decode('utf-8')
            return True
        except Exception:
            pass
        if b'\x00' in sample:
            return False
        text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
        return all(b in text_chars for b in sample)

    def _format_size(self, bytes_):
        if bytes_ < 1024:
            return '{} B'.format(bytes_)
        if bytes_ < 1024 * 1024:
            return '{:.1f} KB'.format(bytes_ / 1024)
        if bytes_ < 1024 * 1024 * 1024:
            return '{:.1f} MB'.format(bytes_ / 1024 / 1024)
        return '{:.1f} GB'.format(bytes_ / 1024 / 1024 / 1024)
