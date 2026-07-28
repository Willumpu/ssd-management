"""
测试跟踪管理视图
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View, ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from .models import (
    TestItem, TestAbnormalRelation, TestComment, TestItemLog, SankeyNode, SankeyEdge,
    TestItemAbnormalAnalysis, AbnormalReason
)
from .forms import TestCommentForm, TestItemForm, TestItemCreateForm, TestItemAbnormalAnalysisForm
from fae.models import Customer, User
from django.utils import timezone


def _save_test_parameters(request, test_item, form):
    """保存测试项动态参数值"""
    from .models import TestParameterDefinition, TestItemParameter
    params = TestParameterDefinition.objects.filter(is_active=True)
    for param in params:
        field_key = f'param_{param.param_key}'
        if field_key in form.cleaned_data:
            value = form.cleaned_data[field_key]
            if value is not None and str(value) != '':
                TestItemParameter.objects.update_or_create(
                    test_item=test_item,
                    parameter=param,
                    defaults={'value': str(value)}
                )
            else:
                TestItemParameter.objects.filter(test_item=test_item, parameter=param).delete()


def _link_abnormal_samples_to_test(test_item, samples, user):
    """将异常样品关联到测试项，并创建测试记录"""
    from abnormal.models import TestRecordEntry
    
    linked_count = 0
    for sample in samples:
        # 创建测试项与异常样品的关联
        TestAbnormalRelation.objects.get_or_create(
            test_item=test_item,
            abnormal_sample=sample
        )
        
        # 更新异常样品的所属测试项
        sample.test_item = test_item
        sample.save(update_fields=['test_item'])
        
        # 为该异常样品创建测试记录（避免重复）
        solution_name = str(test_item.solution) if test_item.solution else '无'
        record_content = (
            f"加入测试项 {test_item.test_number}，"
            f"测试内容：{test_item.get_test_content_display()}，"
            f"测试方案：{solution_name}"
        )
        
        exists = TestRecordEntry.objects.filter(
            abnormal_sample=sample,
            content__icontains=test_item.test_number,
            operator=user,
            created_at__gte=timezone.now() - timezone.timedelta(minutes=5)
        ).exists()
        
        if not exists:
            TestRecordEntry.objects.create(
                abnormal_sample=sample,
                record_time=timezone.now(),
                content=record_content,
                operator=user
            )
        
        linked_count += 1
    
    return linked_count


def handle_test_item_abnormal_group(request, test_item, form, is_create=False):
    """处理测试项与异常样品组的关联及自动创建测试记录"""
    abnormal_group = form.cleaned_data.get('abnormal_group')
    if not abnormal_group:
        return
    
    linked_count = _link_abnormal_samples_to_test(test_item, abnormal_group.samples.all(), request.user)
    
    # 更新异常样品组的所属测试项
    if is_create and not abnormal_group.test_item:
        abnormal_group.test_item = test_item
        abnormal_group.save(update_fields=['test_item'])
    
    if linked_count > 0:
        messages.success(
            request,
            f'已关联异常样品组 {abnormal_group.group_number} 的 {linked_count} 个样品，并自动添加测试记录'
        )


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
        from collections import defaultdict
        relations = self.object.abnormal_relations.select_related(
            'abnormal_sample__group', 'abnormal_sample__customer'
        ).all()
        grouped = defaultdict(list)
        ungrouped = []
        for relation in relations:
            sample = relation.abnormal_sample
            if sample.group:
                grouped[sample.group].append(sample)
            else:
                ungrouped.append(sample)
        context['grouped_abnormals'] = list(grouped.items())
        context['ungrouped_abnormals'] = ungrouped
        context['comments'] = self.object.comments.select_related('author').all()
        context['comment_form'] = TestCommentForm()
        # 测试参数
        context['test_parameters'] = self.object.parameters.select_related('parameter').all()
        # 异常样品分析（只读展示）
        context['abnormal_analyses'] = self.object.abnormal_analyses.select_related('reason', 'created_by').all()
        context['abnormal_analysis_total'] = (
            self.object.abnormal_analyses.aggregate(total=Sum('quantity'))['total'] or 0
        )
        return context


class TestItemCreateView(LoginRequiredMixin, CreateView):
    """创建测试项"""
    model = TestItem
    template_name = 'testing/test_form.html'
    form_class = TestItemCreateForm
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['tracker'].queryset = User.objects.filter(role__in=['fae', 'fae_leader'])
        
        # 限制异常样品为当前 FAE 任务下的样品
        fae_task_id = self.request.GET.get('fae_task')
        if fae_task_id:
            try:
                from fae.models import FAETask
                from abnormal.models import AbnormalSample
                fae_task = FAETask.objects.get(pk=fae_task_id)
                form.fields['abnormal_samples'].queryset = AbnormalSample.objects.filter(
                    customer=fae_task.customer,
                    status__in=['pending_analysis', 'retesting'],
                ).select_related('group', 'customer').order_by('-created_at')
            except FAETask.DoesNotExist:
                pass
        
        # 如果从桑基图节点跳转过来，自动预选节点上的异常样品
        source_sankey_node_id = self.request.GET.get('source_sankey_node_id') or self.request.GET.get('sankey_node')
        if fae_task_id and source_sankey_node_id:
            try:
                source_node = SankeyNode.objects.get(pk=source_sankey_node_id, fae_task_id=fae_task_id)
                sample_ids = list(source_node.abnormal_samples.all().values_list('pk', flat=True))
                if sample_ids:
                    initial_ids = [str(i) for i in sample_ids]
                    form.initial['abnormal_samples'] = initial_ids
                    form.fields['abnormal_samples'].initial = initial_ids
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f'自动预选异常样品失败 (node={source_sankey_node_id}, task={fae_task_id}): {e}')
        
        # 如果从项目跳转过来，自动填充项目
        project_id = self.request.GET.get('project')
        if project_id:
            from project.models import Project
            form.fields['project'].queryset = Project.objects.filter(pk=project_id)
            form.initial['project'] = int(project_id)
            # project 字段在模板中根据 request.GET.project 条件隐藏/显示
        
        # 如果从 FAE 任务跳转过来，自动填充客户和负责人
        fae_task_id = self.request.GET.get('fae_task')
        if fae_task_id:
            from fae.models import FAETask
            try:
                fae_task = FAETask.objects.get(pk=fae_task_id)
                form.fields['customer'].initial = fae_task.customer
                if fae_task.assignee:
                    form.fields['tracker'].initial = fae_task.assignee
            except FAETask.DoesNotExist:
                pass
        
        # 如果从桑基图跳转过来（创建分支测试项）
        source_test_id = self.request.GET.get('source_test')
        branch_type = self.request.GET.get('branch_type')
        if source_test_id:
            try:
                source = TestItem.objects.get(pk=source_test_id)
                form.source_test_id = source.pk
                form.branch_type = branch_type
                form.source_test_obj = source
                # 自动填充来源测试项的信息
                form.fields['customer'].initial = source.customer
                form.fields['project'].initial = source.project
                form.fields['solution'].initial = source.solution
            except TestItem.DoesNotExist:
                pass
        
        # 桑基图跳转时自动填充样品数量和测试内容
        total_samples = self.request.GET.get('total_samples')
        if total_samples:
            form.fields['total_samples'].initial = int(total_samples)
        test_content = self.request.GET.get('test_content')
        if test_content:
            form.fields['test_content'].initial = test_content
        
        return form
    
    def form_valid(self, form):
        # 额外校验：从桑基图源节点创建时，样品总数不能超过源节点数量
        fae_task_id = self.request.GET.get('fae_task') or self.request.POST.get('fae_task')
        source_sankey_node_id = (
            self.request.GET.get('source_sankey_node_id') or
            self.request.GET.get('sankey_node') or
            self.request.POST.get('source_sankey_node_id')
        )
        if fae_task_id and source_sankey_node_id:
            try:
                from fae.models import FAETask
                fae_task = FAETask.objects.get(pk=fae_task_id)
                source_node = SankeyNode.objects.get(pk=source_sankey_node_id, fae_task=fae_task)
                total = form.cleaned_data.get('total_samples') or 0
                if total > source_node.quantity:
                    form.add_error(
                        'total_samples',
                        f'样品总数不能超过来源节点数量（{source_node.quantity}片）'
                    )
                    return self.form_invalid(form)
            except (FAETask.DoesNotExist, SankeyNode.DoesNotExist):
                pass
        
        form.instance.created_by = self.request.user
        form.instance.status = 'not_started'
        response = super().form_valid(form)
        
        # 保存测试参数
        _save_test_parameters(self.request, self.object, form)
        
        # 保存桑基图源流关系
        source_test_id = getattr(form, 'source_test_id', None) or self.request.POST.get('source_test')
        branch_type = getattr(form, 'branch_type', None) or self.request.POST.get('branch_type')
        if source_test_id:
            try:
                source = TestItem.objects.get(pk=source_test_id)
                self.object.source_tests.add(source)
                if branch_type in ['passed', 'failed', 'initial']:
                    self.object.branch_type = branch_type
                    self.object.save(update_fields=['branch_type'])
            except TestItem.DoesNotExist:
                pass
        
        # 处理异常样品组关联
        handle_test_item_abnormal_group(self.request, self.object, form, is_create=True)
        
        # 处理手动选择的异常样品关联
        abnormal_samples = form.cleaned_data.get('abnormal_samples')
        if abnormal_samples:
            linked = _link_abnormal_samples_to_test(self.object, abnormal_samples, self.request.user)
            if linked:
                messages.success(self.request, f'已关联 {linked} 个异常样品')
        
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
        
        # 如果从合流/子分类节点跳转过来
        source_sankey_node_id = self.request.GET.get('source_sankey_node_id') or self.request.POST.get('source_sankey_node_id')
        if fae_task_id and source_sankey_node_id:
            try:
                from fae.models import FAETask
                fae_task = FAETask.objects.get(pk=fae_task_id)
                source_node = SankeyNode.objects.get(pk=source_sankey_node_id, fae_task=fae_task)
                # 记录桑基图源节点，后续同步以此为依据
                self.object.source_sankey_node = source_node
                self.object.save(update_fields=['source_sankey_node'])
                import logging
                create_logger = logging.getLogger(__name__)
                create_logger.warning(
                    f'[TestItemCreateView] set source_sankey_node '
                    f'test={self.object.test_number} node_id={source_node.id} '
                    f'node_type={source_node.node_type}'
                )
                
                if source_node.node_type in ('merged', 'subcategory'):
                    # 合流/子分类节点本身作为初始节点，直接关联测试项
                    source_node.test_item = self.object
                    source_node.save(update_fields=['test_item'])
                else:
                    # 其他节点：创建 initial 节点和边
                    init = SankeyNode.objects.filter(
                        fae_task=fae_task, test_item=self.object, node_type='initial'
                    ).first()
                    if not init:
                        init = SankeyNode.objects.create(
                            fae_task=fae_task,
                            label=f"初始 {self.object.test_number} ({self.object.total_samples}片)",
                            quantity=self.object.total_samples,
                            node_type='initial',
                            test_item=self.object,
                        )
                    SankeyEdge.objects.get_or_create(
                        fae_task=fae_task,
                        source_node=source_node,
                        target_node=init,
                        defaults={
                            'label': self.object.get_test_content_display(),
                            'quantity': self.object.total_samples,
                            'test_item': self.object,
                        }
                    )
                # 自动关联节点上的异常样品
                linked = _link_abnormal_samples_to_test(self.object, source_node.abnormal_samples.all(), self.request.user)
                if linked:
                    messages.success(self.request, f'已自动关联 {linked} 个异常样品')
            except (SankeyNode.DoesNotExist, FAETask.DoesNotExist):
                pass
        
        # 同步桑基图节点和流（创建时若已填写 pass/fail 数量，立即生成对应节点）
        try:
            sync_test_item_to_sankey(self.object)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'创建测试项后同步桑基图失败: {e}', exc_info=True)
        
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


def sync_test_item_to_sankey(test_item):
    """根据测试项的 passed_samples/abnormal_samples_count 增量同步桑基图节点和流"""
    from fae.models import FAETask
    fae_task = test_item.fae_tasks.first()
    if not fae_task:
        return
    
    from django.db import transaction
    with transaction.atomic():
        sources = list(test_item.source_tests.all())
        test_name = test_item.get_test_content_display()
        
        # 确定源节点
        source_node = None
        
        import logging
        sankey_logger = logging.getLogger(__name__)
        sankey_logger.warning(
            f'[sync_test_item_to_sankey] start '
            f'test={test_item.test_number} '
            f'source_sankey_node_id={test_item.source_sankey_node_id} '
            f'sources={[s.pk for s in sources]} branch_type={test_item.branch_type}'
        )
        
        # 0. 如果测试项记录了来源桑基图节点（子分类/异常分类/合流），直接使用该节点作为源
        if test_item.source_sankey_node and test_item.source_sankey_node.fae_task_id == fae_task.id:
            source_node = test_item.source_sankey_node
            sankey_logger.warning(
                f'[sync_test_item_to_sankey] use source_sankey_node '
                f'id={source_node.id}, type={source_node.node_type}, label={source_node.label}'
            )
            # 当测试项已有 pass/fail 结果时，删除作为过渡的旧 initial 节点
            if test_item.passed_samples > 0 or test_item.abnormal_samples_count > 0:
                SankeyNode.objects.filter(
                    fae_task=fae_task, test_item=test_item, node_type='initial'
                ).delete()
        # 1. 兼容旧数据：从子分类/异常分类/合流节点创建的测试项可能没有记录 source_sankey_node，
        #    通过已存在的边来推断源节点
        elif special_source_edge := SankeyEdge.objects.filter(
            fae_task=fae_task,
            source_node__node_type__in=('subcategory', 'abnormal_category', 'merged')
        ).filter(
            Q(test_item=test_item) | Q(target_node__test_item=test_item)
        ).select_related('source_node').first():
            source_node = special_source_edge.source_node
            sankey_logger.warning(
                f'[sync_test_item_to_sankey] use special source edge to node '
                f'id={source_node.id}, type={source_node.node_type}, label={source_node.label}'
            )
            # 当测试项已有 pass/fail 结果时，删除作为过渡的旧 initial 节点
            if test_item.passed_samples > 0 or test_item.abnormal_samples_count > 0:
                SankeyNode.objects.filter(
                    fae_task=fae_task, test_item=test_item, node_type='initial'
                ).delete()
        # 2. 检查是否有 merged/subcategory 节点直接关联到该测试项
        elif merged_source := SankeyNode.objects.filter(
            fae_task=fae_task, test_item=test_item, node_type__in=('merged', 'subcategory')
        ).first():
            source_node = merged_source
            # 删除可能已存在的旧 initial 节点（兼容旧数据）
            SankeyNode.objects.filter(
                fae_task=fae_task, test_item=test_item, node_type='initial'
            ).delete()
        elif not sources:
            # 3. 检查旧数据：initial 节点是否有来自特殊节点的入边
            existing_init = SankeyNode.objects.filter(
                fae_task=fae_task, test_item=test_item, node_type='initial'
            ).first()
            if existing_init:
                incoming = SankeyEdge.objects.filter(
                    fae_task=fae_task, target_node=existing_init, source_node__node_type__in=('merged', 'subcategory')
                ).first()
                if incoming:
                    # 旧数据：删除 initial，改用 merged 节点
                    existing_init.delete()
                    source_node = incoming.source_node
                    source_node.test_item = test_item
                    source_node.save(update_fields=['test_item'])
                else:
                    # 普通初始测试
                    existing_init.quantity = test_item.total_samples
                    existing_init.label = f"初始 {test_item.test_number} ({test_item.total_samples}片)"
                    existing_init.save(update_fields=['quantity', 'label'])
                    source_node = existing_init
            else:
                # 新建 initial 节点
                source_node = SankeyNode.objects.create(
                    fae_task=fae_task,
                    label=f"初始 {test_item.test_number} ({test_item.total_samples}片)",
                    quantity=test_item.total_samples,
                    node_type='initial',
                    test_item=test_item,
                )
        else:
            # 3. 分支测试：源节点是 source_tests 第一个的 pass 或 fail 节点
            src = sources[0]
            src_node_type = 'pass' if test_item.branch_type == 'passed' else 'fail'
            source_node = SankeyNode.objects.filter(
                fae_task=fae_task, test_item=src, node_type=src_node_type
            ).first()
        
        sankey_logger.warning(
            f'[sync_test_item_to_sankey] final source_node='
            f'{source_node.id if source_node else None} '
            f'type={source_node.node_type if source_node else None}'
        )
        
        # 清理该测试项 pass/fail 节点的旧入边，避免源节点变更后残留错误连线
        if source_node:
            SankeyEdge.objects.filter(
                fae_task=fae_task,
                target_node__test_item=test_item,
                target_node__node_type__in=('pass', 'fail')
            ).exclude(source_node=source_node).delete()
        
        # 处理 PASS 节点和边
        if test_item.passed_samples > 0:
            pass_node = SankeyNode.objects.filter(
                fae_task=fae_task, test_item=test_item, node_type='pass'
            ).first()
            if not pass_node:
                pass_node = SankeyNode.objects.create(
                    fae_task=fae_task,
                    label=f"PASS {test_item.test_number} - {test_name} ({test_item.passed_samples}片)",
                    quantity=test_item.passed_samples,
                    node_type='pass',
                    test_item=test_item,
                )
            else:
                pass_node.quantity = test_item.passed_samples
                pass_node.label = f"PASS {test_item.test_number} - {test_name} ({test_item.passed_samples}片)"
                pass_node.save(update_fields=['quantity', 'label'])
            
            if source_node:
                edge = SankeyEdge.objects.filter(
                    fae_task=fae_task, source_node=source_node, target_node=pass_node
                ).first()
                if not edge:
                    SankeyEdge.objects.create(
                        fae_task=fae_task, label=test_name,
                        source_node=source_node, target_node=pass_node,
                        quantity=test_item.passed_samples, test_item=test_item,
                    )
                else:
                    edge.quantity = test_item.passed_samples
                    edge.label = test_name
                    edge.save(update_fields=['quantity', 'label'])
        else:
            SankeyNode.objects.filter(
                fae_task=fae_task, test_item=test_item, node_type='pass'
            ).delete()
        
        # 处理 FAIL 节点和边
        if test_item.abnormal_samples_count > 0:
            fail_node = SankeyNode.objects.filter(
                fae_task=fae_task, test_item=test_item, node_type='fail'
            ).first()
            if not fail_node:
                fail_node = SankeyNode.objects.create(
                    fae_task=fae_task,
                    label=f"FAIL {test_item.test_number} - {test_name} ({test_item.abnormal_samples_count}片)",
                    quantity=test_item.abnormal_samples_count,
                    node_type='fail',
                    test_item=test_item,
                )
            else:
                fail_node.quantity = test_item.abnormal_samples_count
                fail_node.label = f"FAIL {test_item.test_number} - {test_name} ({test_item.abnormal_samples_count}片)"
                fail_node.save(update_fields=['quantity', 'label'])
            
            if source_node:
                edge = SankeyEdge.objects.filter(
                    fae_task=fae_task, source_node=source_node, target_node=fail_node
                ).first()
                if not edge:
                    SankeyEdge.objects.create(
                        fae_task=fae_task, label=test_name,
                        source_node=source_node, target_node=fail_node,
                        quantity=test_item.abnormal_samples_count, test_item=test_item,
                    )
                else:
                    edge.quantity = test_item.abnormal_samples_count
                    edge.label = test_name
                    edge.save(update_fields=['quantity', 'label'])
        else:
            SankeyNode.objects.filter(
                fae_task=fae_task, test_item=test_item, node_type='fail'
            ).delete()


class TestItemUpdateView(LoginRequiredMixin, UpdateView):
    """更新测试项"""
    model = TestItem
    template_name = 'testing/test_form.html'
    form_class = TestItemForm
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['tracker'].queryset = User.objects.filter(role__in=['fae', 'fae_leader'])
        
        # 限制异常样品为当前 FAE 任务下的样品
        fae_task = self.object.fae_tasks.first()
        if fae_task:
            from abnormal.models import AbnormalSample
            from django.db.models import Q
            base_qs = AbnormalSample.objects.filter(
                customer=fae_task.customer,
                status__in=['pending_analysis', 'retesting'],
            )
            linked_ids = list(self.object.abnormal_relations.values_list('abnormal_sample_id', flat=True))
            if linked_ids:
                base_qs = (base_qs | AbnormalSample.objects.filter(pk__in=linked_ids)).distinct()
            form.fields['abnormal_samples'].queryset = base_qs.select_related('group', 'customer').order_by('-created_at')
        
        # 设置已关联的异常样品为初始值
        if self.object.pk:
            form.fields['abnormal_samples'].initial = [
                str(i) for i in self.object.abnormal_relations.values_list('abnormal_sample_id', flat=True)
            ]
        return form
    
    def form_valid(self, form):
        # 获取原始数据
        old_instance = self.get_object()
        old_status = old_instance.status
        
        # 额外校验：如果测试项有来源桑基图节点，样品总数不能超过源节点数量
        if old_instance.source_sankey_node:
            source_node = old_instance.source_sankey_node
            total = form.cleaned_data.get('total_samples') or 0
            if total > source_node.quantity:
                form.add_error(
                    'total_samples',
                    f'样品总数不能超过来源节点数量（{source_node.quantity}片）'
                )
                return self.form_invalid(form)
        
        response = super().form_valid(form)
        
        # 保存测试参数
        _save_test_parameters(self.request, self.object, form)
        
        # 处理异常样品组关联（更新时如果更换了组）
        handle_test_item_abnormal_group(self.request, self.object, form, is_create=False)
        
        # 处理手动选择的异常样品关联
        abnormal_samples = form.cleaned_data.get('abnormal_samples')
        if abnormal_samples:
            linked = _link_abnormal_samples_to_test(self.object, abnormal_samples, self.request.user)
            if linked:
                messages.success(self.request, f'已关联 {linked} 个异常样品')
        
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
            'testing_samples': '测试中数量',
            'retesting_samples': '复测中数量',
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
        
        # 记录项目时间线（仅状态变更时）
        if self.object.project and old_status != new_status:
            from project.signals import record_project_activity
            status_dict = dict(TestItem.TEST_STATUS_CHOICES)
            old_status_display = status_dict.get(old_status, old_status)
            new_status_display = status_dict.get(new_status, new_status)
            record_project_activity(
                project=self.object.project,
                actor=self.request.user,
                action='status_change',
                instance=self.object,
                description=f"状态：{old_status_display} → {new_status_display}"
            )
        
        # 同步桑基图节点和流
        try:
            sync_test_item_to_sankey(self.object)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'同步测试项到桑基图失败: {e}', exc_info=True)
        
        messages.success(self.request, '测试项更新成功')
        return response
    
    def get_success_url(self):
        return reverse_lazy('testing:test_detail', kwargs={'pk': self.object.pk})


class AbnormalReasonCreateAPIView(LoginRequiredMixin, View):
    """FAE主管/管理员创建异常原因"""
    def post(self, request):
        if not (request.user.is_fae_leader() or request.user.is_admin_role()):
            return JsonResponse({'success': False, 'error': '只有FAE主管或管理员可以创建异常原因'}, status=403)
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': '无效的JSON数据'})
        
        name = (data.get('name') or '').strip()
        if not name:
            return JsonResponse({'success': False, 'error': '异常原因名称不能为空'})
        
        if AbnormalReason.objects.filter(name=name).exists():
            return JsonResponse({'success': False, 'error': '该异常原因已存在'})
        
        reason = AbnormalReason.objects.create(
            name=name,
            description=(data.get('description') or '').strip(),
            is_active=True
        )
        return JsonResponse({'success': True, 'id': reason.id, 'name': reason.name})


class TestItemAbnormalAnalysisCreateView(LoginRequiredMixin, View):
    """为测试项添加异常样品分析记录"""
    def post(self, request, pk):
        test_item = get_object_or_404(TestItem, pk=pk)
        form = TestItemAbnormalAnalysisForm(request.POST, test_item=test_item)
        if form.is_valid():
            analysis = form.save(commit=False)
            analysis.test_item = test_item
            analysis.created_by = request.user
            try:
                analysis.save()
                messages.success(request, '异常样品分析已添加')
            except ValidationError as e:
                messages.error(request, '; '.join(e.messages))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    label = form.fields[field].label if field in form.fields else field
                    messages.error(request, f'{label}: {error}')
        return redirect('testing:test_detail', pk=pk)


class TestItemAbnormalAnalysisUpdateView(LoginRequiredMixin, View):
    """更新异常样品分析记录"""
    def post(self, request, pk):
        analysis = get_object_or_404(TestItemAbnormalAnalysis, pk=pk)
        test_item = analysis.test_item
        form = TestItemAbnormalAnalysisForm(request.POST, instance=analysis, test_item=test_item)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, '异常样品分析已更新')
            except ValidationError as e:
                messages.error(request, '; '.join(e.messages))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    label = form.fields[field].label if field in form.fields else field
                    messages.error(request, f'{label}: {error}')
        return redirect('testing:test_detail', pk=test_item.pk)


class TestItemAbnormalAnalysisDeleteView(LoginRequiredMixin, View):
    """删除异常样品分析记录"""
    def post(self, request, pk):
        analysis = get_object_or_404(TestItemAbnormalAnalysis, pk=pk)
        test_item = analysis.test_item
        analysis.delete()
        messages.success(request, '异常样品分析已删除')
        return redirect('testing:test_detail', pk=test_item.pk)


class TestItemCountUpdateView(LoginRequiredMixin, View):
    """AJAX 更新测试项数量字段（通过/异常/测试中/复测中）"""
    COUNT_FIELDS = {
        'passed_samples': '通过数量',
        'abnormal_samples_count': '异常数量',
        'testing_samples': '测试中数量',
        'retesting_samples': '复测中数量',
    }
    
    def post(self, request, pk):
        test_item = get_object_or_404(TestItem, pk=pk)
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': '无效的JSON数据'})
        
        field = data.get('field')
        value = data.get('value')
        
        if field not in self.COUNT_FIELDS:
            return JsonResponse({'success': False, 'error': '不允许编辑的字段'})
        
        try:
            value = int(value)
            if value < 0:
                return JsonResponse({'success': False, 'error': '数量不能为负数'})
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'error': '数量必须是整数'})
        
        old_value = getattr(test_item, field)
        setattr(test_item, field, value)
        
        try:
            test_item.save(update_fields=[field])
        except ValidationError as e:
            return JsonResponse({'success': False, 'error': '; '.join(e.messages)})
        
        # 记录日志
        label = self.COUNT_FIELDS[field]
        TestItemLog.objects.create(
            test_item=test_item,
            operator=request.user,
            action=f'更新{label}',
            comment=f'{label}: {old_value} → {value}',
            old_status=test_item.status,
            new_status=test_item.status,
        )
        
        # 同步桑基图
        try:
            sync_test_item_to_sankey(test_item)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'同步测试项到桑基图失败: {e}', exc_info=True)
        
        return JsonResponse({'success': True, 'field': field, 'value': value})


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


from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt


@method_decorator(xframe_options_exempt, name='dispatch')
class TestFlowSankeyView(LoginRequiredMixin, View):
    """测试流程桑基图（基于FAE任务）- 交互式编辑器"""
    template_name = 'testing/test_flow_sankey.html'
    
    def get(self, request, fae_task_id):
        from fae.models import FAETask
        task = get_object_or_404(FAETask, pk=fae_task_id)
        
        # 如果没有桑基图数据，或用户强制重新初始化
        if request.GET.get('reinit') == '1':
            task.sankey_edges.all().delete()
            task.sankey_nodes.all().delete()
        
        if not task.sankey_nodes.exists():
            self._init_sankey_from_tests(task)
        
        from abnormal.models import AbnormalSample
        context = {
            'fae_task': task,
            'test_content_choices': TestItem.TEST_CONTENT_CHOICES,
            'test_count': task.test_items.count(),
            'abnormal_samples': list(AbnormalSample.objects.filter(
                sankey_nodes__fae_task=task
            ).values('id', 'sample_number', 'status')),
            'abnormal_reasons': list(AbnormalReason.objects.filter(is_active=True).order_by('order', 'name').values('id', 'name')),
        }
        return render(request, self.template_name, context)
    
    def _init_sankey_from_tests(self, task):
        """从现有测试项初始化桑基图"""
        from django.db import transaction
        tests = list(task.test_items.prefetch_related('source_tests').order_by('created_at'))
        
        with transaction.atomic():
            test_to_initial_node = {}
            test_to_pass_node = {}
            test_to_fail_node = {}
            
            # 1. 创建所有节点
            for test in tests:
                if not test.source_tests.exists():
                    init = SankeyNode.objects.create(
                        fae_task=task,
                        label=f"初始 {test.test_number} ({test.total_samples}片)",
                        quantity=test.total_samples,
                        node_type='initial',
                        test_item=test,
                    )
                    test_to_initial_node[test.id] = init
                
                if test.passed_samples > 0:
                    pn = SankeyNode.objects.create(
                        fae_task=task,
                        label=f"PASS {test.test_number} - {test.get_test_content_display()} ({test.passed_samples}片)",
                        quantity=test.passed_samples,
                        node_type='pass',
                        test_item=test,
                    )
                    test_to_pass_node[test.id] = pn
                
                if test.abnormal_samples_count > 0:
                    fn = SankeyNode.objects.create(
                        fae_task=task,
                        label=f"FAIL {test.test_number} - {test.get_test_content_display()} ({test.abnormal_samples_count}片)",
                        quantity=test.abnormal_samples_count,
                        node_type='fail',
                        test_item=test,
                    )
                    test_to_fail_node[test.id] = fn
            
            # 2. 创建边
            for test in tests:
                test_name = test.get_test_content_display()
                sources = [s for s in test.source_tests.all()]
                
                if not sources:
                    # 初始测试
                    init = test_to_initial_node.get(test.id)
                    if init:
                        if test.passed_samples > 0 and test.id in test_to_pass_node:
                            SankeyEdge.objects.create(
                                fae_task=task, label=test_name,
                                source_node=init, target_node=test_to_pass_node[test.id],
                                quantity=test.passed_samples, test_item=test,
                            )
                        if test.abnormal_samples_count > 0 and test.id in test_to_fail_node:
                            SankeyEdge.objects.create(
                                fae_task=task, label=test_name,
                                source_node=init, target_node=test_to_fail_node[test.id],
                                quantity=test.abnormal_samples_count, test_item=test,
                            )
                else:
                    # 分支测试
                    for src in sources:
                        src_pass = test_to_pass_node.get(src.id)
                        src_fail = test_to_fail_node.get(src.id)
                        
                        if test.branch_type == 'passed' and src_pass and test.id in test_to_pass_node:
                            SankeyEdge.objects.create(
                                fae_task=task, label=test_name,
                                source_node=src_pass, target_node=test_to_pass_node[test.id],
                                quantity=test.passed_samples, test_item=test,
                            )
                        elif test.branch_type == 'failed' and src_fail:
                            if test.id in test_to_pass_node:
                                SankeyEdge.objects.create(
                                    fae_task=task, label=test_name,
                                    source_node=src_fail, target_node=test_to_pass_node[test.id],
                                    quantity=test.passed_samples, test_item=test,
                                )
                            if test.id in test_to_fail_node:
                                SankeyEdge.objects.create(
                                    fae_task=task, label=test_name,
                                    source_node=src_fail, target_node=test_to_fail_node[test.id],
                                    quantity=test.abnormal_samples_count, test_item=test,
                                )


@method_decorator(xframe_options_exempt, name='dispatch')
class SankeyEmbedView(LoginRequiredMixin, View):
    """测试流程桑基图（嵌入版，用于iframe内嵌）"""
    template_name = 'testing/test_flow_sankey_embed.html'
    
    def get(self, request, fae_task_id):
        from fae.models import FAETask
        task = get_object_or_404(FAETask, pk=fae_task_id)
        
        # 如果没有桑基图数据，自动初始化
        if not task.sankey_nodes.exists():
            # 复用 TestFlowSankeyView 的初始化逻辑
            init_view = TestFlowSankeyView()
            init_view._init_sankey_from_tests(task)
        
        from abnormal.models import AbnormalSample
        context = {
            'fae_task': task,
            'test_content_choices': TestItem.TEST_CONTENT_CHOICES,
            'test_count': task.test_items.count(),
            'abnormal_samples': list(AbnormalSample.objects.filter(
                sankey_nodes__fae_task=task
            ).values('id', 'sample_number', 'status')),
            'abnormal_reasons': list(AbnormalReason.objects.filter(is_active=True).order_by('order', 'name').values('id', 'name')),
        }
        return render(request, self.template_name, context)

# ========== 桑基图 API 视图 ==========

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


class SankeyDataView(LoginRequiredMixin, View):
    """获取桑基图数据（JSON）"""
    def get(self, request, fae_task_id):
        from fae.models import FAETask
        task = get_object_or_404(FAETask, pk=fae_task_id)
        
        nodes_raw = list(task.sankey_nodes.order_by('created_at'))
        edges_raw = list(task.sankey_edges.select_related('source_node', 'target_node', 'test_item').prefetch_related('test_item__parameters__parameter'))
        
        node_map = {n.id: i for i, n in enumerate(nodes_raw)}
        
        # 计算节点深度（BFS）
        node_depths = {}
        incoming_edges = {n.id: [] for n in nodes_raw}
        for edge in edges_raw:
            if edge.target_node_id in incoming_edges:
                incoming_edges[edge.target_node_id].append(edge.source_node_id)
        
        # 没有入边的节点深度为 0
        for node in nodes_raw:
            if not incoming_edges[node.id]:
                node_depths[node.id] = 0
        
        # BFS 计算其他节点深度（子分类使用小增量，形成紧凑分支效果）
        changed = True
        while changed:
            changed = False
            for edge in edges_raw:
                src_depth = node_depths.get(edge.source_node_id)
                if src_depth is not None:
                    target_id = edge.target_node_id
                    target_node = edge.target_node
                    if target_node is None:
                        continue
                    increment = 0.8 if target_node.node_type in ('subcategory', 'abnormal_category') else 1.0
                    new_depth = src_depth + increment
                    if target_id not in node_depths or new_depth > node_depths[target_id]:
                        node_depths[target_id] = new_depth
                        changed = True
        
        color_map = {
            'initial': '#94a3b8',
            'pass': '#22c55e',
            'fail': '#ef4444',
            'subcategory': '#f97316',
            'abnormal_category': '#ef4444',
            'merged': '#8b5cf6',
        }
        
        # 辅助函数：动态生成节点显示名称
        def get_node_display_name(node):
            if node.node_type == 'pass' and node.test_item:
                total = node.test_item.total_samples or 1
                pct = round(node.quantity / total * 100)
                return f"PASS({node.quantity}片)\n占比：{pct}%"
            if node.node_type == 'fail' and node.test_item:
                total = node.test_item.total_samples or 1
                pct = round(node.quantity / total * 100)
                return f"FAIL({node.quantity}片)\n占比：{pct}%"
            if node.node_type in ('subcategory', 'abnormal_category'):
                return f"{node.category_reason}\n({node.quantity}片)"
            if node.node_type == 'merged':
                return f"({node.quantity}片)"
            return node.label
        
        # 先生成所有节点的显示名称
        node_display_names = {n.id: get_node_display_name(n) for n in nodes_raw}
        
        # 批量获取节点关联的异常样品ID
        node_abnormal_ids = {}
        for node in nodes_raw:
            node_abnormal_ids[node.id] = list(node.abnormal_samples.values_list('id', flat=True))
        
        nodes = []
        for node in nodes_raw:
            nodes.append({
                'name': node_display_names[node.id],
                'id': node.id,
                'quantity': node.quantity,
                'nodeType': node.node_type,
                'categoryReason': node.category_reason,
                'testItemId': node.test_item_id,
                'abnormalIds': node_abnormal_ids.get(node.id, []),
                'depth': node_depths.get(node.id, 0),
                'customY': node.custom_y,
                'itemStyle': {'color': color_map.get(node.node_type, '#94a3b8')},
            })
        
        links = []
        for edge in edges_raw:
            if edge.source_node_id in node_map and edge.target_node_id in node_map:
                # 动态生成流显示名称
                flow_name = edge.label
                if edge.test_item and edge.test_item.solution:
                    flow_name = f"{edge.test_item.get_test_content_display()}\n{edge.test_item.solution.software_version}"
                elif edge.test_item:
                    flow_name = edge.test_item.get_test_content_display()
                # 测试项参数
                test_item_params = []
                if edge.test_item:
                    test_item_params = [
                        {'name': p.parameter.name, 'value': p.value, 'unit': p.parameter.unit}
                        for p in edge.test_item.parameters.all()
                    ]
                links.append({
                    'source': node_display_names[edge.source_node_id],
                    'target': node_display_names[edge.target_node_id],
                    'sourceId': edge.source_node_id,
                    'targetId': edge.target_node_id,
                    'value': edge.quantity,
                    'quantity': edge.quantity,
                    'name': flow_name,
                    'id': edge.id,
                    'testItemParams': test_item_params,
                })
        
        return JsonResponse({'nodes': nodes, 'links': links})


class SankeyNodeCreateView(LoginRequiredMixin, View):
    """创建测试分支节点 + 流 + 测试项"""
    def post(self, request, fae_task_id):
        from fae.models import FAETask
        task = get_object_or_404(FAETask, pk=fae_task_id)
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': '无效的JSON数据'})
        
        source_node_id = data.get('source_node_id')
        branch_type = data.get('branch_type')  # 'passed' or 'failed'
        quantity = int(data.get('quantity', 0))
        test_content = data.get('test_content', '')
        
        source_node = get_object_or_404(SankeyNode, pk=source_node_id, fae_task=task)
        
        if quantity <= 0 or quantity > source_node.quantity:
            return JsonResponse({'success': False, 'error': '数量无效'})
        
        from django.db import transaction
        from solution.models import Solution
        with transaction.atomic():
            # 创建测试项
            test_item = TestItem.objects.create(
                test_number=TestItem().generate_test_number(),
                tracker=task.assignee,
                customer=task.customer,
                project=task.project,
                created_by=request.user,
                solution=Solution.objects.first(),
                test_content=test_content,
                total_samples=quantity,
                passed_samples=quantity if branch_type == 'passed' else 0,
                abnormal_samples_count=quantity if branch_type == 'failed' else 0,
                branch_type=branch_type,
                source_sankey_node=source_node,
            )
            
            # 关联到 FAE 任务
            task.test_items.add(test_item)
            
            # 关联源测试项
            if source_node.test_item:
                test_item.source_tests.add(source_node.test_item)
            
            # 创建目标节点
            node_type = 'pass' if branch_type == 'passed' else 'fail'
            label_prefix = 'PASS' if branch_type == 'passed' else 'FAIL'
            target_node = SankeyNode.objects.create(
                fae_task=task,
                label=f"{label_prefix} - {test_item.get_test_content_display()} ({quantity}片)",
                quantity=quantity,
                node_type=node_type,
                test_item=test_item,
            )
            
            # 创建流
            SankeyEdge.objects.create(
                fae_task=task,
                label=test_item.get_test_content_display(),
                source_node=source_node,
                target_node=target_node,
                quantity=quantity,
                test_item=test_item,
            )
        
        return JsonResponse({'success': True, 'node_id': target_node.id, 'test_item_id': test_item.id})


class SankeyNodeSplitView(LoginRequiredMixin, View):
    """拆分子类节点 / 异常分类节点"""
    def post(self, request, node_id):
        source_node = get_object_or_404(SankeyNode, pk=node_id)
        task = source_node.fae_task
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': '无效的JSON数据'})
        
        splits = data.get('splits', [])
        edge_label = data.get('edge_label', '子分类')
        
        total = sum(s['quantity'] for s in splits)
        
        # 已存在的子节点（子分类/异常分类）总量
        existing_children_total = source_node.child_nodes.filter(
            node_type__in=('subcategory', 'abnormal_category')
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        # 子节点总量不得超过父节点数量
        if existing_children_total + total > source_node.quantity:
            remaining = max(source_node.quantity - existing_children_total, 0)
            return JsonResponse({
                'success': False,
                'error': f'父节点已分流 {existing_children_total} 片，还可分流 {remaining} 片，当前 {total} 片超出限制'
            })
        
        from django.db import transaction
        with transaction.atomic():
            for split in splits:
                node_type = split.get('node_type', 'subcategory')
                quantity = split['quantity']
                
                if node_type == 'abnormal_category':
                    # 异常分类节点只能从fail节点创建，且必须选择异常原因
                    if source_node.node_type != 'fail':
                        return JsonResponse({'success': False, 'error': '异常分类节点只能从失败节点创建'})
                    
                    reason_id = split.get('reason_id')
                    if not reason_id:
                        return JsonResponse({'success': False, 'error': '请选择异常原因'})
                    
                    try:
                        reason = AbnormalReason.objects.get(pk=int(reason_id), is_active=True)
                    except (AbnormalReason.DoesNotExist, ValueError, TypeError):
                        return JsonResponse({'success': False, 'error': '异常原因不存在'})
                    
                    label = f"{reason.name} ({quantity}片)"
                    category_reason = reason.name
                else:
                    label = f"{split['label']} ({quantity}片)"
                    category_reason = split.get('category_reason', '')
                
                child = SankeyNode.objects.create(
                    fae_task=task,
                    label=label,
                    quantity=quantity,
                    node_type=node_type,
                    category_reason=category_reason,
                    test_item=source_node.test_item,
                )
                child.parent_nodes.add(source_node)
                
                SankeyEdge.objects.create(
                    fae_task=task,
                    label=edge_label,
                    source_node=source_node,
                    target_node=child,
                    quantity=quantity,
                    test_item=source_node.test_item,
                )
                
                # 如果是异常分类节点，自动创建异常分析记录并关联到当前节点
                if node_type == 'abnormal_category' and source_node.test_item and reason:
                    analysis = TestItemAbnormalAnalysis(
                        test_item=source_node.test_item,
                        reason=reason,
                        quantity=quantity,
                        created_by=request.user,
                        sankey_node=child,
                    )
                    analysis.save()
            
            # 父节点数量保持不变，仅做校验
        
        return JsonResponse({'success': True})


class SankeyNodeUpdateView(LoginRequiredMixin, View):
    """更新子分类/异常分类节点的名称和数量（父节点数量保持不变，仅做总量校验）"""
    def post(self, request, node_id):
        node = get_object_or_404(SankeyNode, pk=node_id)
        
        if node.node_type not in ('subcategory', 'abnormal_category'):
            return JsonResponse({'success': False, 'error': '只能编辑子分类或异常分类节点'})
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': '无效的JSON数据'})
        
        new_label = (data.get('label') or '').strip()
        new_quantity = int(data.get('quantity', 0))
        
        if not new_label:
            return JsonResponse({'success': False, 'error': '节点名称不能为空'})
        if new_quantity <= 0:
            return JsonResponse({'success': False, 'error': '数量必须大于0'})
        
        old_quantity = node.quantity
        if new_quantity == old_quantity and new_label == node.label:
            return JsonResponse({'success': True})
        
        # 获取父节点（异常分类/子分类节点应当有且只有一个父节点）
        parent = node.parent_nodes.first()
        if not parent:
            return JsonResponse({'success': False, 'error': '该节点没有父节点，无法编辑数量'})
        
        from django.db import transaction
        from django.db.models import Sum
        with transaction.atomic():
            # 所有兄弟子节点（子分类+异常分类，不含当前节点）的总量
            siblings_total = SankeyNode.objects.filter(
                parent_nodes=parent,
                node_type__in=('subcategory', 'abnormal_category')
            ).exclude(pk=node.pk).aggregate(total=Sum('quantity'))['total'] or 0
            
            # 子节点总量不得超过父节点数量
            if siblings_total + new_quantity > parent.quantity:
                remaining = max(parent.quantity - siblings_total, 0)
                return JsonResponse({
                    'success': False,
                    'error': f'父节点已分流 {siblings_total} 片，还可分流 {remaining} 片，当前 {new_quantity} 片超出限制'
                })
            
            # 父节点数量保持不变
            
            # 更新当前节点
            node.label = f"{new_label} ({new_quantity}片)"
            node.quantity = new_quantity
            if node.node_type == 'abnormal_category':
                node.category_reason = new_label
            node.save(update_fields=['label', 'quantity', 'category_reason'])
            
            # 同步更新入边的数量
            incoming = SankeyEdge.objects.filter(target_node=node).first()
            if incoming:
                incoming.quantity = new_quantity
                incoming.save(update_fields=['quantity'])
            
            # 如果是异常分类节点，同步更新关联的异常分析记录数量
            if node.node_type == 'abnormal_category':
                analysis = node.abnormal_analyses.first()
                if analysis:
                    analysis.quantity = new_quantity
                    analysis.save(update_fields=['quantity'])
            
            # 如果该节点是某个测试项的 source_sankey_node，重新同步该测试项
            for test_item in node.sourced_test_items.all():
                try:
                    sync_test_item_to_sankey(test_item)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f'同步测试项 {test_item.test_number} 失败: {e}', exc_info=True)
        
        return JsonResponse({'success': True})


class SankeyNodesMergeView(LoginRequiredMixin, View):
    """多节点合流"""
    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': '无效的JSON数据'})
        
        node_ids = data.get('node_ids', [])
        target_label = data.get('target_label', '')
        target_node_type = data.get('target_node_type', 'merged')
        edge_label = data.get('edge_label', '合流')
        
        if len(node_ids) < 2:
            return JsonResponse({'success': False, 'error': '至少需要两个节点'})
        
        nodes = list(SankeyNode.objects.filter(pk__in=node_ids))
        if len(nodes) != len(node_ids):
            return JsonResponse({'success': False, 'error': '部分节点不存在'})
        
        tasks = set(n.fae_task_id for n in nodes)
        if len(tasks) > 1:
            return JsonResponse({'success': False, 'error': '节点必须属于同一任务'})
        
        task = nodes[0].fae_task
        quantities = data.get('quantities', {})
        
        from django.db import transaction
        with transaction.atomic():
            total = 0
            for node in nodes:
                qty = int(quantities.get(str(node.id), node.quantity))
                if qty <= 0 or qty > node.quantity:
                    return JsonResponse({'success': False, 'error': f'节点"{node.label}"的数量无效'})
                total += qty
            
            target = SankeyNode.objects.create(
                fae_task=task,
                label=f"{target_label} ({total}片)",
                quantity=total,
                node_type=target_node_type,
            )
            
            # 自动将被合流节点的异常样品绑定到合流节点
            all_samples = []
            for node in nodes:
                all_samples.extend(node.abnormal_samples.all())
            if all_samples:
                target.abnormal_samples.add(*all_samples)
            
            for node in nodes:
                qty = int(quantities.get(str(node.id), node.quantity))
                SankeyEdge.objects.create(
                    fae_task=task,
                    label=edge_label,
                    source_node=node,
                    target_node=target,
                    quantity=qty,
                )
                # 合流后保持源节点数量不变
        
        return JsonResponse({'success': True, 'node_id': target.id})


class SankeyNodeDeleteView(LoginRequiredMixin, View):
    """删除节点及其子节点"""
    def post(self, request, node_id):
        node = get_object_or_404(SankeyNode, pk=node_id)
        task = node.fae_task
        
        def delete_recursive(n):
            # 先删除子节点
            for child in n.child_nodes.all():
                delete_recursive(child)
            # 如果是异常分类节点，同步删除测试项中关联的异常分析记录
            if n.node_type == 'abnormal_category':
                n.abnormal_analyses.all().delete()
            # 删除关联的边
            n.outgoing_edges.all().delete()
            n.incoming_edges.all().delete()
            n.delete()
        
        delete_recursive(node)
        return JsonResponse({'success': True})


class SankeyNodeAbnormalAttachView(LoginRequiredMixin, View):
    """同步节点与异常样品的绑定关系"""
    def post(self, request, node_id):
        node = get_object_or_404(SankeyNode, pk=node_id)
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': '无效的JSON数据'})
        
        abnormal_ids = data.get('abnormal_ids', [])
        abnormal_sample_id = data.get('abnormal_sample_id')
        abnormal_group_id = data.get('abnormal_group_id')
        
        if abnormal_sample_id:
            abnormal_ids = [abnormal_sample_id]
        
        # 如果传入了组ID，把组内所有样品加入目标列表
        if abnormal_group_id:
            from abnormal.models import AbnormalSampleGroup
            try:
                group = AbnormalSampleGroup.objects.get(pk=abnormal_group_id)
                group_sample_ids = list(group.samples.values_list('id', flat=True))
                abnormal_ids = list(set(abnormal_ids + group_sample_ids))
            except AbnormalSampleGroup.DoesNotExist:
                return JsonResponse({'success': False, 'error': '异常样品组不存在'})
        
        from abnormal.models import AbnormalSample
        target_ids = set(int(i) for i in abnormal_ids if i)
        
        # 父节点校验：有父节点时只能从父节点绑定的样品中分配
        parent_nodes = list(node.parent_nodes.all())
        if parent_nodes:
            parent_sample_ids = set()
            for p in parent_nodes:
                parent_sample_ids.update(p.abnormal_samples.values_list('id', flat=True))
            
            if not parent_sample_ids:
                return JsonResponse({'success': False, 'error': '父节点未绑定异常样品，无法绑定'})
            
            if len(target_ids) > len(parent_sample_ids):
                return JsonResponse({
                    'success': False,
                    'error': f'绑定数量（{len(target_ids)}）超过父节点异常样品数量（{len(parent_sample_ids)}）'
                })
            
            if not target_ids.issubset(parent_sample_ids):
                return JsonResponse({'success': False, 'error': '只能绑定父节点已绑定的异常样品'})
            
            # 兄弟节点校验：同一父节点下的其他子节点已绑定的样品不能再绑定
            sibling_bound_ids = set()
            for p in parent_nodes:
                for sibling in p.child_nodes.all():
                    if sibling.pk != node.pk:
                        sibling_bound_ids.update(sibling.abnormal_samples.values_list('id', flat=True))
            
            conflict_ids = target_ids & sibling_bound_ids
            if conflict_ids:
                return JsonResponse({
                    'success': False,
                    'error': f'有 {len(conflict_ids)} 个样品已被兄弟节点绑定'
                })
        
        current_ids = set(node.abnormal_samples.values_list('id', flat=True))
        
        to_add = target_ids - current_ids
        to_remove = current_ids - target_ids
        
        if to_add:
            samples_to_add = AbnormalSample.objects.filter(pk__in=to_add)
            node.abnormal_samples.add(*samples_to_add)
        if to_remove:
            samples_to_remove = AbnormalSample.objects.filter(pk__in=to_remove)
            node.abnormal_samples.remove(*samples_to_remove)
        
        return JsonResponse({
            'success': True,
            'added': len(to_add),
            'removed': len(to_remove),
        })


class SankeyNodeGroupCreateView(LoginRequiredMixin, View):
    """在子类节点或异常分类节点上创建异常样品组，并自动绑定组内所有样品到该节点"""
    def post(self, request, node_id):
        node = get_object_or_404(SankeyNode, pk=node_id)
        
        # 只允许子类节点和异常分类节点创建异常样品组
        if node.node_type not in ('subcategory', 'abnormal_category'):
            return JsonResponse({'success': False, 'error': '只有子类节点或异常分类节点可以创建异常样品组'})
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': '无效的JSON数据'})
        
        from abnormal.models import AbnormalSampleGroup, AbnormalSample
        from abnormal.forms import AbnormalSampleGroupForm
        
        # 准备表单数据
        form_data = {
            'customer': data.get('customer_id'),
            'priority': data.get('priority', 'normal'),
            'status': data.get('status', 'pending_analysis'),
            'abnormal_description': data.get('abnormal_description', ''),
            'total_count': int(data.get('total_count', 1)),
        }
        
        # 可选字段
        if data.get('project_id'):
            form_data['project'] = data.get('project_id')
        if data.get('solution_id'):
            form_data['solution'] = data.get('solution_id')
        if data.get('assignee_id'):
            form_data['assignee'] = data.get('assignee_id')
        if data.get('test_item_id'):
            form_data['test_item'] = data.get('test_item_id')
        
        form = AbnormalSampleGroupForm(form_data)
        if not form.is_valid():
            errors = []
            for field, errs in form.errors.items():
                errors.append(f"{form.fields[field].label if field in form.fields else field}: {', '.join(errs)}")
            return JsonResponse({'success': False, 'error': '；'.join(errors)})
        
        # 保存组
        group = form.save(commit=False)
        group.created_by = request.user
        group.save()
        
        # 批量创建异常样品
        total_count = form.cleaned_data.get('total_count', 1)
        created_samples = []
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
                created_by=request.user,
            )
            sample.save()
            created_samples.append(sample)
            
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
        
        # 将所有样品绑定到桑基图节点
        for sample in created_samples:
            node.abnormal_samples.add(sample)
        
        return JsonResponse({
            'success': True,
            'group_id': group.id,
            'group_number': group.group_number,
            'sample_count': len(created_samples)
        })


class SankeyNodeUpdateYView(LoginRequiredMixin, View):
    """更新节点自定义Y坐标"""
    def post(self, request, node_id):
        node = get_object_or_404(SankeyNode, pk=node_id)
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': '无效的JSON数据'})
        
        custom_y = data.get('custom_y')
        if custom_y is None:
            node.custom_y = None
        else:
            try:
                node.custom_y = float(custom_y)
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'error': 'Y坐标必须是数字'})
        
        node.save(update_fields=['custom_y'])
        return JsonResponse({'success': True, 'custom_y': node.custom_y})


class SankeyNodeAbnormalDetachView(LoginRequiredMixin, View):
    """解除节点与异常样品的关联"""
    def post(self, request, node_id):
        node = get_object_or_404(SankeyNode, pk=node_id)
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': '无效的JSON数据'})
        
        abnormal_id = data.get('abnormal_id')
        if not abnormal_id:
            return JsonResponse({'success': False, 'error': '请选择异常样品'})
        
        node.abnormal_samples.remove(abnormal_id)
        return JsonResponse({'success': True})


class SankeyTaskAbnormalsView(LoginRequiredMixin, View):
    """获取任务下所有与桑基图节点关联的异常样品"""
    def get(self, request, fae_task_id):
        from fae.models import FAETask
        task = get_object_or_404(FAETask, pk=fae_task_id)
        
        from abnormal.models import AbnormalSample
        abnormals = AbnormalSample.objects.filter(
            sankey_nodes__fae_task=task
        ).select_related('customer', 'assignee', 'group').prefetch_related('sankey_nodes').distinct()
        
        result = []
        for abn in abnormals:
            result.append({
                'id': abn.id,
                'sample_number': abn.sample_number,
                'status': abn.status,
                'status_display': abn.get_status_display(),
                'priority': abn.priority,
                'priority_display': abn.get_priority_display(),
                'node_ids': list(abn.sankey_nodes.filter(fae_task=task).values_list('id', flat=True)),
                'customer_code': abn.customer.customer_code if abn.customer else '',
                'group_id': abn.group_id,
                'group_number': abn.group.group_number if abn.group else None,
            })
        
        return JsonResponse({'abnormals': result})
