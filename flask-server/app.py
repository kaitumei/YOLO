import logging
# 标准库导入
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
# 第三方扩展导入
from flask_migrate import Migrate
from flask_wtf import CSRFProtect
# 自定义模块导入
from config.prod import DevelopmentConfig
from src.blueprints.check import bp as check_bp
from src.blueprints.cms import bp as cms_bp
from src.blueprints.common import bp as common_bp
from src.blueprints.front import bp as front_bp
from src.blueprints.stream import bp as stream_bp
# 移除微信小程序蓝图导入
from src.utils import commands, hooks
from src.utils.exts import db, cache, csrf, mail, socketio, avatars
from src.utils.bbs_celery import make_celery
from src.utils.stream_utils import stream_manager
import os
from datetime import datetime
from flask_wtf.csrf import generate_csrf
import sys


#------------------------------
# 应用初始化
#------------------------------
app = Flask(__name__)

app.config.from_object(DevelopmentConfig)
app.before_request(hooks.bbs_before_request)    # 请求钩子

#------------------------------
# 配置日志系统
#------------------------------
# 设置日志级别
app.logger.setLevel(logging.INFO)

# 创建文件处理器
if not os.path.exists('logs'):
    os.makedirs('logs')
file_handler = logging.FileHandler('logs/flask_app.log', encoding='utf-8')
file_handler.setLevel(logging.INFO)

# 创建控制台处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)

# 设置日志格式
formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# 添加处理器到logger
app.logger.addHandler(file_handler)
app.logger.addHandler(console_handler)

# 配置stream_utils的logger
stream_logger = logging.getLogger('stream_manager')
stream_logger.setLevel(logging.DEBUG)
stream_logger.addHandler(file_handler)
stream_logger.addHandler(console_handler)

app.logger.info('应用启动')

#------------------------------
# 扩展组件初始化
#------------------------------
db.init_app(app)
migrate = Migrate(app, db) # 数据库配置
cache.init_app(app)# 缓存系统
csrf.init_app(app)# 安全防护
mail.init_app(app)# 邮件系统
socketio.init_app(app, cors_allowed_origins='*',async_mode='eventlet')# WebSocket系统
avatars.init_app(app)# 头像系统
cors = CORS(app, supports_credentials=True,  resources={r"/*": {"origins": "*"}})# 跨域请求

# WebSocket事件处理
@socketio.on('connect')
def handle_connect():
    app.logger.info('WebSocket客户端已连接')

@socketio.on('disconnect')
def handle_disconnect():
    app.logger.info('WebSocket客户端已断开连接')

# 初始化Celery
celery = make_celery(app)
# 添加配置以便Celery命令行工具正确找到应用程序
app.config.update(CELERY_CONFIG_MODULE='celeryconfig')
# 确保Celery使用正确的配置
celery.config_from_object('celeryconfig')

#------------------------------
# 蓝图注册
#------------------------------
app.register_blueprint(cms_bp)     # 内容管理系统路由
app.register_blueprint(common_bp)  # 通用功能路由（登录/注册等）
app.register_blueprint(front_bp)   # 前端展示路由
app.register_blueprint(check_bp)   # 服务状态检查路由
app.register_blueprint(stream_bp)  # 流媒体相关路由

# 配置CSRF以接受AJAX请求
@app.after_request
def add_csrf_header(response):
    response.headers.set('X-CSRFToken', generate_csrf())
    return response

# 定义需要豁免CSRF保护的路径
csrf.exempt(check_bp)  # 豁免整个check蓝图
csrf.exempt(stream_bp)  # 豁免整个stream蓝图

#------------------------------
# 自定义命令行命令
#------------------------------
app.cli.command("create-permission")(commands.create_permission)  # 创建权限
app.cli.command("create-role")(commands.create_role)              # 创建角色
app.cli.command("create-test-user")(commands.create_test_user)    # 创建测试用户
app.cli.command("create-admin")(commands.create_admin)           # 创建管理员账号
app.cli.command("update-permissions")(commands.update_permissions_command)  # 更新角色权限

#------------------------------
# 错误处理器
#------------------------------
app.errorhandler(404)(hooks.bbs_404_error)  # 404页面不存在
app.errorhandler(401)(hooks.bbs_401_error)  # 401未授权访问
app.errorhandler(500)(hooks.bbs_500_error)  # 500服务器内部错误

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                             'favicon.ico', mimetype='image/vnd.microsoft.icon')

#------------------------------
# 主程序入口
#------------------------------
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000,debug=True)



