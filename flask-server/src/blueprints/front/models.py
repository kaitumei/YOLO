from datetime import datetime
from src.utils.exts import db
from shortuuid  import uuid
from werkzeug.security import generate_password_hash, check_password_hash

class UserModel( db.Model):
    """用户模型，存储用户的基本信息和认证信息"""
    __tablename__ = 'users'
    id = db.Column(db.String(100), primary_key=True, default=uuid)  # 用户唯一标识符
    username = db.Column(db.String(50), nullable=False, unique=True)  # 用户名，不可重复
    phone = db.Column(db.String(11), unique=True, nullable=True)  # 手机号字段，唯一
    phone_verified = db.Column(db.Boolean, default=False)  # 手机号验证状态
    _password = db.Column(db.String(200), nullable=False)  # 加密后的密码
    email = db.Column(db.String(50), nullable=True, unique=True)  # 邮箱，唯一
    avatar = db.Column(db.String(100))  # 用户头像路径
    signature = db.Column(db.String(100))  # 个性签名
    join_time = db.Column(db.DateTime, default=datetime.now)  # 注册时间
    last_login = db.Column(db.DateTime)  # 最后登录时间
    is_staff = db.Column(db.Boolean, default=False)  # 是否为工作人员
    is_active = db.Column(db.Boolean, default=True)  # 账户是否激活

    role_id = db.Column(db.Integer, db.ForeignKey('role.id'))  # 角色外键
    role = db.relationship('RoleModel', backref='users')  # 与角色的关联关系

    reset_token = db.Column(db.String(200))   # 密码重置令牌
    token_expiry = db.Column(db.DateTime)     # 令牌过期时间

    def __init__(self,*args,**kwargs):
        """
        初始化用户对象
        - 处理密码加密
        - 设置默认角色为普通用户
        """
        if 'password' in kwargs:
            self.password = kwargs.get('password')
            kwargs.pop('password')
        
        # 如果没有指定角色，则设置为普通用户角色
        if 'role' not in kwargs and 'role_id' not in kwargs:
            from ..cms.models import RoleModel
            normal_user_role = RoleModel.query.filter_by(name='普通用户').first()
            if normal_user_role:
                kwargs['role'] = normal_user_role
        
        super(UserModel,self).__init__(*args,**kwargs)

    @property
    def password(self):
        """密码获取方法，返回加密后的密码"""
        return self._password

    @password.setter
    def password(self, raw_password):
        """
        密码设置方法，对原始密码进行加密处理
        """
        self._password = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        """
        密码验证方法，验证用户输入的原始密码是否正确
        """
        result = check_password_hash(self._password, raw_password)
        return result

    def has_permission(self, permission):
        """
        检查用户是否拥有指定权限
        """
        return permission in [permission.name for permission in self.role.permissions]

class UserLogModel(db.Model):
    """用户日志模型，记录用户的各种操作"""
    __tablename__ = 'user_logs'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # 日志ID，自增
    user_id = db.Column(db.String(100), db.ForeignKey('users.id'), nullable=False)  # 关联的用户ID
    action = db.Column(db.String(50), nullable=False)  # 操作类型：登录、注册、修改密码等
    ip_address = db.Column(db.String(50))  # IP地址
    device_info = db.Column(db.String(200))  # 设备信息
    create_time = db.Column(db.DateTime, default=datetime.now)  # 操作时间
    details = db.Column(db.Text)  # 详细信息，JSON格式

    user = db.relationship('UserModel', backref='logs')  # 与用户的关联关系

class VehicleAppointmentModel(db.Model):
    """车辆预约模型，管理车辆进入预约记录"""
    __tablename__ = 'vehicle_appointments'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # 预约ID，自增
    license_plate = db.Column(db.String(20), nullable=False)  # 车牌号码
    vehicle_type = db.Column(db.String(50), nullable=False)  # 车辆类型
    name = db.Column(db.String(50), nullable=False)  # 预约人姓名
    phone = db.Column(db.String(11), nullable=False)  # 预约人电话
    appointment_date = db.Column(db.Date, nullable=False)  # 预约日期
    appointment_time = db.Column(db.Time, nullable=False)  # 预约时间
    purpose = db.Column(db.String(200), nullable=False)  # 来访目的
    create_time = db.Column(db.DateTime, default=datetime.now)  # 创建时间
    status = db.Column(db.String(20), default='待审核')  # 状态：待审核、已通过、已拒绝
    comment = db.Column(db.Text, nullable=True)  # 审批备注

    # 与UserModel关联，通过phone字段关联到UserModel的phone字段
    user_id = db.Column(db.String(100), db.ForeignKey('users.id'), nullable=True)  # 关联的用户ID
    user = db.relationship('UserModel', backref='vehicle_appointments')  # 与用户的关联关系

    def __init__(self, *args, **kwargs):
        """
        初始化车辆预约对象
        - 根据手机号自动关联用户
        """
        # 如果提供了phone但没有提供user_id，尝试查找对应的用户
        if 'phone' in kwargs and 'user_id' not in kwargs:
            phone = kwargs.get('phone')
            user = UserModel.query.filter_by(phone=phone).first()
            if user:
                kwargs['user_id'] = user.id
        super(VehicleAppointmentModel, self).__init__(*args, **kwargs)

class BannerModel(db.Model):
    """轮播图模型，管理网站首页轮播图"""
    __tablename__ = 'banners'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # 轮播图ID，自增
    title = db.Column(db.String(100))  # 轮播图标题
    image_url = db.Column(db.String(255), nullable=False)  # 图片URL
    link_url = db.Column(db.String(255))  # 点击跳转链接URL
    sort_order = db.Column(db.Integer, default=0)  # 排序顺序，数字越小越靠前
    status = db.Column(db.Integer, default=1)  # 状态：0-禁用，1-启用
    create_time = db.Column(db.DateTime, default=datetime.now)  # 创建时间
    update_time = db.Column(db.DateTime, onupdate=datetime.now)  # 更新时间

    def __repr__(self):
        """对象的字符串表示"""
        return f'<Banner {self.title}>'

class NoticeModel(db.Model):
    """公告模型，管理系统公告"""
    __tablename__ = 'notices'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # 公告ID，自增
    title = db.Column(db.String(100), nullable=False)  # 公告标题
    content = db.Column(db.Text)  # 公告内容
    publish_time = db.Column(db.DateTime, default=datetime.now)  # 发布时间
    end_time = db.Column(db.DateTime)  # 结束时间
    is_important = db.Column(db.Integer, default=0)  # 是否重要：0-普通，1-重要
    status = db.Column(db.Integer, default=1)  # 状态：0-禁用，1-启用
    create_time = db.Column(db.DateTime, default=datetime.now)  # 创建时间
    update_time = db.Column(db.DateTime, onupdate=datetime.now)  # 更新时间

    def __repr__(self):
        """对象的字符串表示"""
        return f'<Notice {self.title}>'

class LogModel(db.Model):
    """系统日志模型，记录系统操作和异常"""
    __tablename__ = 'logs'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # 日志ID，自增
    ip = db.Column(db.String(100))  # 请求IP地址
    user_id = db.Column(db.String(100), db.ForeignKey('users.id'), nullable=True)  # 关联的用户ID
    user = db.relationship('UserModel', backref='system_logs')  # 与用户的关联关系
    message = db.Column(db.Text)  # 日志消息内容
    level = db.Column(db.String(20))  # 日志级别：INFO, WARNING, ERROR, CRITICAL
    path = db.Column(db.String(200))  # 请求路径
    method = db.Column(db.String(10))  # 请求方法：GET, POST等
    status_code = db.Column(db.Integer)  # 响应状态码
    referrer = db.Column(db.String(200))  # 请求来源
    browser = db.Column(db.String(200))  # 浏览器信息
    os = db.Column(db.String(100))  # 操作系统信息
    device = db.Column(db.String(100))  # 设备信息
    create_time = db.Column(db.DateTime, default=datetime.now)  # 创建时间

    def __repr__(self):
        """对象的字符串表示"""
        return f'<Log {self.id}: {self.message[:20]}...>'


