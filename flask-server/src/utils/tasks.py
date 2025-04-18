# from app import celery
# from flask_mail import Message
#
# @celery.task(
#     name='async_mailer',  # 显式命名任务
#     max_retries=3,  # 失败自动重试次数
#     soft_time_limit=10  # 任务超时时间（秒）
# )
#
# def send_mail(to: str, subject: str, body: str) -> None:
#     from exts import mail  # 延迟导入确保在应用上下文中初始化
#
#     # 构建符合RFC 5322标准的邮件对象
#     msg = Message(
#         subject=subject.strip(),  # 去除首尾空白字符
#         recipients=[to.lower()],  # 邮箱地址统一小写处理
#         body=body,
#         charset='utf-8'  # 强制统一编码格式
#     )
#
#     try:
#         mail.send(msg)  # 触发SMTP协议发送
#     except ConnectionRefusedError as e:
#         # 记录邮件服务器连接异常
#         send_mail.retry(exc=e, countdown=30)  # 30秒后重试
#     except TimeoutError as e:
#         # 处理SMTP超时异常
#         send_mail.retry(exc=e, countdown=60)