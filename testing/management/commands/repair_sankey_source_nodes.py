"""
修复从异常分类/子分类/合流节点创建的测试项的 source_sankey_node 字段，
并重新同步这些测试项的桑基图节点。
"""
from django.core.management.base import BaseCommand
from django.db.models import Sum
from testing.models import TestItem, SankeyEdge, SankeyNode


class Command(BaseCommand):
    help = '修复桑基图中异常分类/子分类/合流节点来源的测试项源节点'

    def handle(self, *args, **options):
        repaired = 0
        inferred = 0
        synced = 0

        # 1. 根据已存在的边反推 source_sankey_node（边指向 initial 或 pass/fail）
        for test_item in TestItem.objects.filter(source_sankey_node__isnull=True):
            edge = SankeyEdge.objects.filter(
                fae_task__in=test_item.fae_tasks.all(),
                source_node__node_type__in=('subcategory', 'abnormal_category', 'merged')
            ).filter(
                test_item=test_item
            ).select_related('source_node').first()

            if not edge:
                edge = SankeyEdge.objects.filter(
                    fae_task__in=test_item.fae_tasks.all(),
                    source_node__node_type__in=('subcategory', 'abnormal_category', 'merged'),
                    target_node__test_item=test_item
                ).select_related('source_node').first()

            if edge:
                test_item.source_sankey_node = edge.source_node
                test_item.save(update_fields=['source_sankey_node'])
                repaired += 1
                self.stdout.write(
                    f'已修复 {test_item.test_number} <- {edge.source_node.node_type} '
                    f'node_id={edge.source_node_id} label={edge.source_node.label}'
                )

        # 2. 对仍没有 source_sankey_node 但有 source_tests 的测试项，
        #    尝试根据 FAIL 节点的异常分类子节点数量进行推断
        for test_item in TestItem.objects.filter(
            source_sankey_node__isnull=True,
            source_tests__isnull=False
        ).distinct():
            sources = list(test_item.source_tests.all())
            if not sources:
                continue
            parent = sources[0]
            parent_fail = SankeyNode.objects.filter(
                fae_task__in=test_item.fae_tasks.all(),
                test_item=parent,
                node_type='fail'
            ).first()
            if not parent_fail:
                continue

            # 查找 FAIL 节点下的异常分类/子分类子节点，按数量匹配
            candidates = list(parent_fail.child_nodes.filter(
                node_type__in=('subcategory', 'abnormal_category', 'merged')
            ))
            # 优先匹配数量等于测试项总数的节点
            matched = [n for n in candidates if n.quantity == test_item.total_samples]
            if not matched and candidates:
                # 次优匹配：数量等于 pass+fail 的节点
                total_out = test_item.passed_samples + test_item.abnormal_samples_count
                matched = [n for n in candidates if n.quantity == total_out]
            if not matched and candidates:
                # 最后尝试：只有一个候选
                matched = [candidates[0]] if len(candidates) == 1 else []

            if matched:
                source_node = matched[0]
                test_item.source_sankey_node = source_node
                test_item.save(update_fields=['source_sankey_node'])
                inferred += 1
                self.stdout.write(
                    f'已推断 {test_item.test_number} <- {source_node.node_type} '
                    f'node_id={source_node.id} label={source_node.label}'
                )

        # 3. 自动打断 source_sankey_node 是当前测试项 pass/fail 节点后代的循环
        #    删除从当前测试项 pass/fail 指向 source_sankey_node 的边，使其恢复为独立的入口节点
        cycles_broken = 0
        for test_item in TestItem.objects.filter(source_sankey_node__isnull=False):
            for task in test_item.fae_tasks.all():
                sn = test_item.source_sankey_node
                if sn.fae_task_id != task.id:
                    continue
                own_pf = SankeyNode.objects.filter(
                    fae_task=task, test_item=test_item, node_type__in=('pass', 'fail')
                )
                own_pf_ids = set(own_pf.values_list('id', flat=True))
                descendants = set()
                queue = list(own_pf_ids)
                while queue:
                    nid = queue.pop(0)
                    if nid in descendants:
                        continue
                    descendants.add(nid)
                    for cid in SankeyNode.objects.filter(parent_nodes__id=nid).values_list('id', flat=True):
                        if cid not in descendants:
                            queue.append(cid)
                if sn.id in descendants - own_pf_ids:
                    removed, _ = SankeyEdge.objects.filter(
                        fae_task=task,
                        source_node__test_item=test_item,
                        source_node__node_type__in=('pass', 'fail'),
                        target_node=sn
                    ).delete()
                    # 同时移除 parent_nodes 多对多关系
                    for pf in own_pf:
                        sn.parent_nodes.remove(pf)
                    cycles_broken += 1
                    self.stdout.write(
                        f'已打断循环：删除 {test_item.test_number} 的 pass/fail 节点 '
                        f'指向 source_sankey_node({sn.id}) 的边及父子关系'
                    )

        # 4. 对所有测试项重新同步桑基图（包括普通初始测试，以便恢复被误删的 initial 节点）
        from testing.views import sync_test_item_to_sankey
        for test_item in TestItem.objects.all():
            try:
                sync_test_item_to_sankey(test_item)
                synced += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'同步 {test_item.test_number} 失败: {e}'
                ))

        # 4. 扫描并报告剩余脏数据
        cycle_issues = []
        quantity_issues = []
        for test_item in TestItem.objects.all():
            for task in test_item.fae_tasks.all():
                # source_sankey_node 是否是自己 pass/fail 节点的后代（形成环）
                if test_item.source_sankey_node and test_item.source_sankey_node.fae_task_id == task.id:
                    sn = test_item.source_sankey_node
                    own_pf = SankeyNode.objects.filter(
                        fae_task=task, test_item=test_item, node_type__in=('pass', 'fail')
                    )
                    own_pf_ids = set(own_pf.values_list('id', flat=True))
                    descendants = set()
                    queue = list(own_pf_ids)
                    while queue:
                        nid = queue.pop(0)
                        if nid in descendants:
                            continue
                        descendants.add(nid)
                        for cid in SankeyNode.objects.filter(parent_nodes__id=nid).values_list('id', flat=True):
                            if cid not in descendants:
                                queue.append(cid)
                    if sn.id in descendants - own_pf_ids:
                        cycle_issues.append(
                            f'{test_item.test_number} 的 source_sankey_node({sn.id} {sn.node_type}) '
                            f'是当前测试项 pass/fail 节点的后代，可能形成循环连线'
                        )

                # FAIL 节点数量是否小于子分类/异常分类节点总和
                for fail_node in SankeyNode.objects.filter(
                    fae_task=task, test_item=test_item, node_type='fail'
                ):
                    child_sum = fail_node.child_nodes.filter(
                        node_type__in=('subcategory', 'abnormal_category')
                    ).aggregate(total=Sum('quantity'))['total'] or 0
                    if child_sum > fail_node.quantity:
                        quantity_issues.append(
                            f'{test_item.test_number} 的 FAIL 节点({fail_node.id}) 数量 '
                            f'{fail_node.quantity} 小于子节点总和 {child_sum}'
                        )

        self.stdout.write(self.style.SUCCESS(
            f'修复完成：{repaired} 个根据边修复，{inferred} 个根据图结构推断，'
            f'{cycles_broken} 个循环已打断，{synced} 个重新同步桑基图'
        ))

        if cycle_issues:
            self.stdout.write(self.style.WARNING(
                f'发现 {len(cycle_issues)} 个 source_sankey_node 循环，需要手动检查：'
            ))
            for issue in cycle_issues:
                self.stdout.write(self.style.WARNING(f'  - {issue}'))

        if quantity_issues:
            self.stdout.write(self.style.WARNING(
                f'发现 {len(quantity_issues)} 个 FAIL 节点数量不足，需要手动调整：'
            ))
            for issue in quantity_issues:
                self.stdout.write(self.style.WARNING(f'  - {issue}'))

        if not cycle_issues and not quantity_issues:
            self.stdout.write(self.style.SUCCESS('未发现 source_sankey_node 循环或 FAIL 节点数量不足。'))
