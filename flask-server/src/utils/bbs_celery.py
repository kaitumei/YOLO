from celery import Celery
from flask_mail import Message
from src.utils.exts import mail
import logging
import os

# 定义任务函数
def send_mail(recipient, subject, body):
    """
    发送邮件的函数
    :param recipient: 收件人邮箱
    :param subject: 邮件主题
    :param body: 邮件内容
    :return: 发送结果
    """
    # 检查是否在开发环境中
    debug_mode = os.environ.get('FLASK_ENV') == 'development' or os.environ.get('FLASK_DEBUG') == '1'
    
    try:
        # 记录邮件内容到日志(仅用于调试)
        logging.info(f"准备发送邮件到: {recipient}, 主题: {subject}")
        
        # 在调试模式下，可以选择跳过实际的邮件发送，直接返回成功
        if debug_mode:
            logging.info(f"调试模式：模拟发送邮件成功 - 收件人: {recipient}, 内容: {body}")
            return True
        
        message = Message(subject=subject, recipients=[recipient], body=body)
        mail.send(message)
        logging.info(f'邮件发送成功！收件人: {recipient}')
        return True
    except Exception as e:
        logging.error(f"邮件发送失败: {str(e)}", exc_info=True)
        # 在调试模式下，即使发送失败也返回成功
        if debug_mode:
            logging.warning(f"调试模式：邮件发送失败，但模拟发送成功")
            return True
        return False

# 创建 Celery 应用
def make_celery(app):
    celery = Celery(
        app.import_name,
        backend=app.config.get('result_backend'),
        broker=app.config.get('broker_url')
    )
    
    # 使用Flask应用配置来配置Celery
    celery.conf.update(app.config)
    
    # 明确设置任务模块，使Celery能够找到任务
    celery.conf.update({
        'imports': ('src.utils.bbs_celery',),
        'task_serializer': 'json',
        'result_serializer': 'json',
        'accept_content': ['json'],
        'enable_utc': True,
    })

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    
    # 注册任务
    @celery.task(name='send_mail')
    def task_send_mail(recipient, subject, body):
        return send_mail(recipient, subject, body)
    
    return celery


