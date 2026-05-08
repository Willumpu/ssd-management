import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ssd_management.settings_production')

# Gunicorn 配置文件 - 针对 2GB 内存优化
bind = "127.0.0.1:8000"
workers = 4  # 4个workers
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50

# 内存优化
timeout = 30
keepalive = 5

# 日志
errorlog = "/var/log/ssd_management/gunicorn.error.log"
accesslog = "/var/log/ssd_management/gunicorn.access.log"
loglevel = "warning"

# 进程名称
proc_name = "ssd_management"
