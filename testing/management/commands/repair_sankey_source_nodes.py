"""
修复从异常分类/子分类/合流节点创建的测试项的 source_sankey_node 字段，
并重新同步这些测试项的桑基图节点。
"""
from django.core.management.base import BaseCommand
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

        # 3. 对所有存在 source_sankey_node 的测试项重新同步桑基图
        from testing.views import sync_test_item_to_sankey
        for test_item in TestItem.objects.filter(source_sankey_node__isnull=False):
            try:
                sync_test_item_to_sankey(test_item)
                synced += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'同步 {test_item.test_number} 失败: {e}'
                ))

        self.stdout.write(self.style.SUCCESS(
            f'修复完成：{repaired} 个根据边修复，{inferred} 个根据图结构推断，'
            f'{synced} 个重新同步桑基图'
        ))
