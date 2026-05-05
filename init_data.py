"""
SSD 管理平台初始化数据脚本
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ssd_management.settings')
django.setup()

from fae.models import User, Customer
from solution.models import ControllerModel, FlashModel, PCBModel


def create_superuser():
    """创建超级管理员"""
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser(
            username='admin',
            email='admin@ssd-tech.com',
            password='admin123',
            role='admin',
            department='管理部'
        )
        print('[OK] 超级管理员创建成功: admin / admin123')
    else:
        print('[OK] 超级管理员已存在')


def create_fae_users():
    """创建FAE用户"""
    fae_data = [
        {'username': 'fae01', 'name': '张工', 'role': 'fae'},
        {'username': 'fae02', 'name': '李工', 'role': 'fae'},
        {'username': 'fae03', 'name': '王工', 'role': 'fae'},
        {'username': 'fae_leader', 'name': 'FAE主管', 'role': 'fae_leader'},
    ]
    
    for data in fae_data:
        if not User.objects.filter(username=data['username']).exists():
            User.objects.create_user(
                username=data['username'],
                email=f"{data['username']}@ssd-tech.com",
                password='123456',
                first_name=data['name'],
                role=data['role'],
                department='FAE部'
            )
            print(f'[OK] FAE用户创建成功: {data["username"]} / 123456')
        else:
            print(f'[OK] FAE用户已存在: {data["username"]}')


def create_rd_users():
    """创建研发用户"""
    rd_data = [
        {'username': 'rd01', 'name': '陈工', 'role': 'rd'},
        {'username': 'rd02', 'name': '刘工', 'role': 'rd'},
        {'username': 'rd_leader', 'name': '研发主管', 'role': 'rd_leader'},
    ]
    
    for data in rd_data:
        if not User.objects.filter(username=data['username']).exists():
            User.objects.create_user(
                username=data['username'],
                email=f"{data['username']}@ssd-tech.com",
                password='123456',
                first_name=data['name'],
                role=data['role'],
                department='研发部'
            )
            print(f'[OK] 研发用户创建成功: {data["username"]} / 123456')
        else:
            print(f'[OK] 研发用户已存在: {data["username"]}')


def create_warehouse_user():
    """创建仓库用户"""
    if not User.objects.filter(username='warehouse').exists():
        User.objects.create_user(
            username='warehouse',
            email='warehouse@ssd-tech.com',
            password='123456',
            first_name='仓管员',
            role='warehouse',
            department='仓库部'
        )
        print('[OK] 仓库用户创建成功: warehouse / 123456')
    else:
        print('[OK] 仓库用户已存在')


def create_customers():
    """创建客户数据"""
    customer_codes = [
        'A02', 'A03', 'A04', 'A05', 'A06', 'A07', 'A08', 'A09',
        'A10', 'A11', 'A12', 'A13', 'A14', 'A15', 'A16', 'A17',
        'A18', 'A19', 'A20', 'A21', 'A22', 'A23',
    ]
    
    for code in customer_codes:
        if not Customer.objects.filter(customer_code=code).exists():
            Customer.objects.create(customer_code=code)
            print(f'[OK] 客户创建成功: {code}')
        else:
            print(f'[OK] 客户已存在: {code}')


def create_controller_models():
    """创建主控型号"""
    controllers = [
        {'name': 'SM2268XT', 'description': '慧荣 PCIe 4.0 主控'},
        {'name': 'SM2268XT2', 'description': '慧荣 PCIe 4.0 主控升级版'},
        {'name': 'SM2262EN', 'description': '慧荣 PCIe 3.0 主控'},
        {'name': 'SM2320', 'description': '慧荣 USB 3.2 主控'},
        {'name': 'RTS5765', 'description': '瑞昱 PCIe 4.0 主控'},
        {'name': 'RTS5766', 'description': '瑞昱 PCIe 4.0 主控升级版'},
        {'name': 'PS5026-E26', 'description': '群联 PCIe 5.0 主控'},
        {'name': 'PS5021-E21', 'description': '群联 PCIe 4.0 主控'},
        {'name': 'IG5236', 'description': '英韧 PCIe 4.0 主控'},
        {'name': 'MAP1602', 'description': '联芸 PCIe 4.0 主控'},
    ]
    
    for data in controllers:
        if not ControllerModel.objects.filter(name=data['name']).exists():
            ControllerModel.objects.create(
                name=data['name'],
                description=data['description'],
                is_active=True
            )
            print(f'[OK] 主控型号创建成功: {data["name"]}')
        else:
            print(f'[OK] 主控型号已存在: {data["name"]}')


def create_flash_models():
    """创建Flash型号"""
    flash_models = [
        {'name': 'B27A', 'description': '铠侠 B27A'},
        {'name': 'B27B', 'description': '铠侠 B27B'},
        {'name': 'B47R', 'description': '铠侠 B47R'},
        {'name': 'B58R', 'description': '铠侠 B58R'},
        {'name': 'TAS', 'description': '东芝 TAS'},
        {'name': 'TAS_PLUS', 'description': '东芝 TAS+'},
        {'name': 'H27QDG', 'description': '海力士 H27QDG'},
        {'name': 'H27TDG', 'description': '海力士 H27TDG'},
        {'name': 'MT29F', 'description': '美光 MT29F'},
        {'name': 'MT29F512', 'description': '美光 MT29F512'},
    ]
    
    for data in flash_models:
        if not FlashModel.objects.filter(name=data['name']).exists():
            FlashModel.objects.create(
                name=data['name'],
                description=data['description'],
                is_active=True
            )
            print(f'[OK] Flash型号创建成功: {data["name"]}')
        else:
            print(f'[OK] Flash型号已存在: {data["name"]}')


def create_pcb_models():
    """创建PCB型号"""
    pcb_models = [
        {'name': 'PCB-2280-V1.0', 'description': '2280尺寸 V1.0'},
        {'name': 'PCB-2280-V1.1', 'description': '2280尺寸 V1.1'},
        {'name': 'PCB-2280-V2.0', 'description': '2280尺寸 V2.0'},
        {'name': 'PCB-2242-V1.0', 'description': '2242尺寸 V1.0'},
        {'name': 'PCB-2230-V1.0', 'description': '2230尺寸 V1.0'},
        {'name': 'PCB-22110-V1.0', 'description': '22110尺寸 V1.0'},
        {'name': 'PCB-UFD-V1.0', 'description': 'U盘专用 V1.0'},
        {'name': 'PCB-CFE-V1.0', 'description': 'CFexpress专用 V1.0'},
    ]
    
    for data in pcb_models:
        if not PCBModel.objects.filter(name=data['name']).exists():
            PCBModel.objects.create(
                name=data['name'],
                description=data['description'],
                is_active=True
            )
            print(f'[OK] PCB型号创建成功: {data["name"]}')
        else:
            print(f'[OK] PCB型号已存在: {data["name"]}')


def main():
    print('=' * 50)
    print('SSD Management Platform Initialization')
    print('=' * 50)
    print()
    
    create_superuser()
    print()
    create_fae_users()
    print()
    create_rd_users()
    print()
    create_warehouse_user()
    print()
    create_customers()
    print()
    create_controller_models()
    print()
    create_flash_models()
    print()
    create_pcb_models()
    
    print()
    print('=' * 50)
    print('Initialization Complete!')
    print('=' * 50)


if __name__ == '__main__':
    main()
