"""
项目时间线自动记录信号
当各模块的条目创建/删除时，自动记录到项目时间线
更新由各模块的 UpdateView 手动记录（可获取详细变更内容）
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import ActivityTimeline

MODULE_CONFIG = {
    'fae.faetask': ('fae_task', 'task_number', 'FAE任务'),
    'testing.testitem': ('test_item', 'test_number', '测试跟踪'),
    'abnormal.abnormalsample': ('abnormal_sample', 'sample_number', '异常样品'),
    'solution.solution': ('solution', 'solution_number', '方案'),
    'rd_requirement.rdrequirement': ('rd_requirement', 'requirement_number', '研发需求'),
    'sample_shipment.samplematerial': ('sample_material', 'material_number', '样品物料'),
    'sample_shipment.materialtransfer': ('material_transfer', 'transfer_number', '样品调拨'),
}


def _get_module_info(instance):
    """获取实例对应的模块类型、标识字段名、显示名称"""
    model_path = f"{instance._meta.app_label}.{instance._meta.model_name}"
    return MODULE_CONFIG.get(model_path)


def _get_actor(instance):
    """从实例中获取操作人"""
    for attr in ['created_by', 'operator', 'author', 'assignee', 'uploaded_by', 'reported_by']:
        if hasattr(instance, attr):
            val = getattr(instance, attr, None)
            if val:
                return val
    return None


def _get_subtitle(instance, module_type):
    """获取条目的概述/副标题"""
    try:
        if module_type == 'fae_task':
            return getattr(instance, 'summary', '') or ''
        elif module_type == 'test_item':
            return instance.get_test_content_display() if hasattr(instance, 'get_test_content_display') else ''
        elif module_type == 'abnormal_sample':
            return instance.customer.customer_code if hasattr(instance, 'customer') and instance.customer else ''
        elif module_type == 'solution':
            parts = []
            if hasattr(instance, 'controller_model') and instance.controller_model:
                parts.append(instance.controller_model.name)
            if hasattr(instance, 'flash_model') and instance.flash_model:
                parts.append(instance.flash_model.name)
            return '/'.join(parts)
        elif module_type == 'rd_requirement':
            return getattr(instance, 'title', '') or ''
        elif module_type == 'sample_material':
            return getattr(instance, 'name', '') or ''
        elif module_type == 'material_transfer':
            return instance.material.name if hasattr(instance, 'material') and instance.material else ''
    except Exception:
        pass
    return ''


def build_create_description(instance, module_type):
    """根据模块类型构建创建时的详细描述"""
    desc_parts = []

    if module_type == 'fae_task':
        if hasattr(instance, 'customer') and instance.customer:
            desc_parts.append(f"客户：{instance.customer.customer_code}")
        if hasattr(instance, 'assignee') and instance.assignee:
            desc_parts.append(f"负责人：{instance.assignee.get_full_name() or instance.assignee.username}")
        if hasattr(instance, 'task_type'):
            desc_parts.append(f"类型：{instance.get_task_type_display()}")

    elif module_type == 'test_item':
        if hasattr(instance, 'customer') and instance.customer:
            desc_parts.append(f"客户：{instance.customer.customer_code}")
        if hasattr(instance, 'tracker') and instance.tracker:
            desc_parts.append(f"跟踪人：{instance.tracker.get_full_name() or instance.tracker.username}")

    elif module_type == 'abnormal_sample':
        if hasattr(instance, 'get_priority_display'):
            desc_parts.append(f"优先级：{instance.get_priority_display()}")
        if hasattr(instance, 'test_item') and instance.test_item:
            desc_parts.append(f"关联测试：{instance.test_item.test_number}")

    elif module_type == 'solution':
        if hasattr(instance, 'controller_model') and instance.controller_model:
            desc_parts.append(f"主控：{instance.controller_model.name}")
        if hasattr(instance, 'flash_model') and instance.flash_model:
            desc_parts.append(f"Flash：{instance.flash_model.name}")
        if hasattr(instance, 'get_status_display'):
            desc_parts.append(f"状态：{instance.get_status_display()}")

    elif module_type == 'rd_requirement':
        if hasattr(instance, 'get_requirement_type_display'):
            desc_parts.append(f"类型：{instance.get_requirement_type_display()}")
        if hasattr(instance, 'get_priority_display'):
            desc_parts.append(f"优先级：{instance.get_priority_display()}")
        if hasattr(instance, 'assignee') and instance.assignee:
            desc_parts.append(f"负责人：{instance.assignee.get_full_name() or instance.assignee.username}")

    elif module_type == 'sample_material':
        if hasattr(instance, 'get_category_display'):
            desc_parts.append(f"类别：{instance.get_category_display()}")
        if hasattr(instance, 'related_customer') and instance.related_customer:
            desc_parts.append(f"归属方：{instance.related_customer.customer_code}")

    elif module_type == 'material_transfer':
        if hasattr(instance, 'from_warehouse') and instance.from_warehouse:
            desc_parts.append(f"来源：{instance.from_warehouse.name}")
        if hasattr(instance, 'to_warehouse') and instance.to_warehouse:
            desc_parts.append(f"目标：{instance.to_warehouse.name}")
        if hasattr(instance, 'quantity'):
            desc_parts.append(f"数量：{instance.quantity}")
        if hasattr(instance, 'tracking_info') and instance.tracking_info:
            desc_parts.append(f"物流：{instance.tracking_info}")

    return ' | '.join(desc_parts) if desc_parts else ''


def record_project_activity(project, actor, action, instance, description=''):
    """公共函数：手动记录项目活动（供各 UpdateView 调用）"""
    if not project:
        return
    module_info = _get_module_info(instance)
    if not module_info:
        return
    module_type, id_field, display_name = module_info
    title = getattr(instance, id_field, str(instance))
    subtitle = _get_subtitle(instance, module_type)
    ActivityTimeline.objects.create(
        project=project,
        actor=actor,
        action=action,
        module_type=module_type,
        object_id=instance.pk,
        title=title,
        subtitle=subtitle,
        description=description,
    )


@receiver(post_save)
def record_create(sender, instance, created, **kwargs):
    """记录创建"""
    if not created:
        return
    model_path = f"{sender._meta.app_label}.{sender._meta.model_name}"
    if model_path not in MODULE_CONFIG:
        return
    project = getattr(instance, 'project', None)
    if not project:
        return

    module_info = _get_module_info(instance)
    if not module_info:
        return
    module_type, id_field, display_name = module_info

    actor = _get_actor(instance) or project.created_by
    description = build_create_description(instance, module_type)
    subtitle = _get_subtitle(instance, module_type)

    ActivityTimeline.objects.create(
        project=project,
        actor=actor,
        action='create',
        module_type=module_type,
        object_id=instance.pk,
        title=getattr(instance, id_field, str(instance)),
        subtitle=subtitle,
        description=description,
    )


@receiver(post_delete)
def record_delete(sender, instance, **kwargs):
    """记录删除"""
    model_path = f"{sender._meta.app_label}.{instance._meta.model_name}"
    if model_path not in MODULE_CONFIG:
        return
    project = getattr(instance, 'project', None)
    if not project:
        return

    module_info = _get_module_info(instance)
    if not module_info:
        return
    module_type, id_field, display_name = module_info
    subtitle = _get_subtitle(instance, module_type)

    ActivityTimeline.objects.create(
        project=project,
        actor=project.created_by,
        action='delete',
        module_type=module_type,
        object_id=0,
        title=getattr(instance, id_field, str(instance)),
        subtitle=subtitle,
        description=f'{display_name} 已删除',
    )
