import os
import sys
from app import celery

# 确保 celery 使用正确的配置
celery.config_from_object('celeryconfig')

if __name__ == '__main__':
    celery.start() 