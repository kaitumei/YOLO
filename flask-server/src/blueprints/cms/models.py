from src.utils.exts import db
from datetime import datetime
from ..common.models import PermissionEnum
import os

class PermissionModel(db.Model):
    __tablename__ = 'permission'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Enum(PermissionEnum), nullable=False, unique=True)

role_permission_table = db.Table(
    "role_permission_table",
    db.Column('role_id', db.Integer, db.ForeignKey('role.id')),
    db.Column('permission_id', db.Integer, db.ForeignKey('permission.id'))
)

class RoleModel(db.Model):
    __tablename__ = 'role'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)
    desc = db.Column(db.String(200), nullable=True)
    create_time = db.Column(db.DateTime, default=datetime.now())

    permissions = db.relationship("PermissionModel", secondary=role_permission_table, backref='roles', lazy='dynamic')

class ContentAccessLog(db.Model):
    """内容访问日志模型，用于记录内容访问量"""
    __tablename__ = 'content_access_logs'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    content_id = db.Column(db.Integer, nullable=False)  # 内容ID
    content_type = db.Column(db.String(20), nullable=False)  # 内容类型，如 'notice', 'article' 等
    user_id = db.Column(db.String(100), db.ForeignKey('users.id'), nullable=True)  # 访问用户ID，可为空（未登录用户）
    ip_address = db.Column(db.String(50))  # 访问IP
    access_time = db.Column(db.DateTime, default=datetime.now)  # 访问时间
    device_info = db.Column(db.String(200))  # 设备信息

    # 关联到用户（如果有）
    user = db.relationship('UserModel', backref='content_access_logs', foreign_keys=[user_id])

class WeChat:
    @staticmethod
    def get_banner_wechat_url(image_path):
        """
        转换Flask轮播图URL为WeChat服务器的URL
        
        例如:
        /static/uploads/banners/20230501123030_example.jpg
        转换为:
        /static/images/20230501123030_example.jpg
        """
        if not image_path:
            return None
            
        if image_path.startswith('/static/uploads/banners/'):
            # 提取文件名
            filename = os.path.basename(image_path)
            # 返回适用于WeChat服务器的路径
            return f'/static/images/{filename}'
        return image_path