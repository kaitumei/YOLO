import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

BASE_DIR = Path(__file__).parent.parent

class BaseConfig:
    """
    基础配置
    """
    # Flask 应用配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default-secret-key')  # 从环境变量获取秘钥
    SESSION_TYPE = 'redis'  # 会话类型
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # SQLAlchemy 追踪修改
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)  # 会话有效期7天
    
    # 安全相关配置
    SESSION_COOKIE_SECURE = True  # 仅通过HTTPS发送cookie
    SESSION_COOKIE_HTTPONLY = True  # 防止JavaScript访问cookie
    SESSION_COOKIE_SAMESITE = 'Lax'  # 防止CSRF攻击
    REMEMBER_COOKIE_SECURE = True  # 记住我功能的cookie也仅通过HTTPS发送
    REMEMBER_COOKIE_HTTPONLY = True  # 防止JavaScript访问记住我cookie
    REMEMBER_COOKIE_SAMESITE = 'Lax'  # 防止CSRF攻击
    
    # 数据库配置
    HOSTNAME = os.environ.get('DB_HOSTNAME')
    PORT = os.environ.get('DB_PORT')
    USERNAME = os.environ.get('DB_USERNAME')
    PASSWORD = os.environ.get('DB_PASSWORD')
    DATABASE = os.environ.get('DB_DATABASE')

    # 邮箱服务配置
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_USE_SSL = True
    MAIL_PORT = os.environ.get('MAIL_PORT')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')

    # 缓存与 Celery 配置
    CACHE_TYPE = 'RedisCache'
    CACHE_REDIS_HOST = os.environ.get('REDIS_HOST')
    CACHE_REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
    CACHE_REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD')

    # Celery 配置
    broker_url = os.environ.get('CELERY_BROKER_URL')
    result_backend = os.environ.get('CELERY_RESULT_BACKEND')

    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
    AVATARS_SAVE_PATH = os.path.join(MEDIA_ROOT, 'avatars')

    UPLOAD_DIRECTORY = os.path.join(BASE_DIR, 'uploads')  # 媒体库上传目录
    UPLOAD_IMAGE_PATH = 'static/common'

    SCREENSHOTS_DIR = os.path.join(BASE_DIR, 'media', 'screenshots')
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

    VIDEO_SAVE_DIR = os.path.join(BASE_DIR, 'media', 'videos')
    
    # Node.js服务器静态文件目录路径
    # NODE_SERVER_STATIC_PATH = os.path.join(BASE_DIR, 'docker/node/static/images')
    
    # WeChat服务器静态文件目录路径(已有配置，这里注释作对比)
    # WECHAT_SERVER_STATIC_PATH = os.path.join(BASE_DIR, 'weixin/server/static/images')

class DevelopmentConfig(BaseConfig):
    """
    开发环境配置
    """
    ENV = 'development'
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://{}:{}@{}:{}/{}?charset=utf8mb4'.format(
        BaseConfig.USERNAME,
        BaseConfig.PASSWORD,
        BaseConfig.HOSTNAME,
        BaseConfig.PORT,
        BaseConfig.DATABASE
    )

class YoloBaseConfig(object):
    UPLOAD_FOLDER = BASE_DIR / 'static/uploads'
    RESULT_FOLDER = BASE_DIR / 'static/results'
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

    URL = os.environ.get('YOLO_URL', 'http://127.0.0.1:5001')  # 从环境变量获取YOLO服务器地址





