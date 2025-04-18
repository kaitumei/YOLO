from config.prod import BaseConfig

# Celery配置
broker_url = BaseConfig.broker_url
result_backend = BaseConfig.result_backend

# 明确指定使用Redis
broker_transport_options = {'visibility_timeout': 3600}  # 1小时
result_expires = 3600  # 结果过期时间1小时

# 任务序列化格式
task_serializer = 'json'
# 结果序列化格式
result_serializer = 'json'
# 接受的内容类型
accept_content = ['json']
# 启用UTC时间
enable_utc = True

# 任务路由
task_routes = {
    'send_mail': {'queue': 'mail'}
}

# 导入任务模块，这样Celery可以找到任务
imports = ('src.utils.bbs_celery',) 