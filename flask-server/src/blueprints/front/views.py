import base64
import os
import random
import re
import string
import time
from datetime import datetime, timedelta
from urllib.parse import quote

from flask import (
    Blueprint, jsonify, send_from_directory, abort,
    current_app, g, render_template, request, 
    redirect, url_for, flash, session
)
from itsdangerous import URLSafeTimedSerializer
from werkzeug.datastructures import CombinedMultiDict
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from src.utils import restful
from src.utils.decorators import login_required
from src.utils.exts import db, cache, avatars
from src.utils.sms import send_sms
from src.utils.captcha import Captcha

from .forms import (
    LoginForm, ChangePasswordForm, RegisterForm, EditProfileForm,
    ForgotPasswordForm, ResetPasswordForm, PhoneRegisterForm
)
from .models import UserModel, BannerModel, NoticeModel
from ..cms.models import RoleModel, ContentAccessLog


# 定义全局变量
start_time = datetime.now()


# 辅助函数
def is_allowed_file(filename):
    """检查文件类型是否被允许"""
    # 允许的文件扩展名
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}
    
    # 获取文件扩展名
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    # 检查文件扩展名是否在允许的列表中
    if ext in ALLOWED_EXTENSIONS:
        return True
        
    # 特殊处理：允许avatars目录中的所有文件（头像）
    if filename.startswith('avatars/'):
        return True
        
    return False


def generate_reset_token(email):
    """生成密码重置令牌（有效期1小时）"""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='password-reset')


def verify_reset_token(token, max_age=3600):
    """验证重置令牌"""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='password-reset', max_age=max_age)
        return UserModel.query.filter_by(email=email).first()
    except:
        return None


def log_content_access(content_id, content_type):
    """
    记录内容访问日志
    :param content_id: 内容ID
    :param content_type: 内容类型，如'notice'、'post'等
    """
    try:
        # 获取用户信息
        user_id = session.get('user_id')
        
        # 获取IP和设备信息
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')
        
        # 创建访问日志
        access_log = ContentAccessLog(
            content_id=content_id,
            content_type=content_type,
            user_id=user_id,
            ip_address=ip_address,
            device_info=user_agent[:200]  # 限制长度
        )
        
        db.session.add(access_log)
        db.session.commit()
    except Exception as e:
        # 处理表不存在的情况，不影响主要功能
        if "doesn't exist" in str(e):
            print(f"内容访问日志表不存在: {str(e)}")
        else:
            # 记录日志失败不应影响正常功能
            print(f"记录内容访问日志失败: {str(e)}")
        
        # 回滚会话
        db.session.rollback()


# 创建蓝图
bp = Blueprint('front', __name__)


# 请求钩子
@bp.before_request
def before_request():
    if 'user_id' in session:
        user = UserModel.query.filter_by(id=session.get('user_id')).first()
        if user:
            g.user = user
        else:
            session.pop('user_id', None)
            g.user = None
    else:
        g.user = None
    # 将avatars对象添加到g中，供模板使用
    g.avatars = avatars


# ---------------------------------------------------------------------------------------------------------- #
# 基本路由
# ---------------------------------------------------------------------------------------------------------- #
@bp.route('/')
def index():
    if not hasattr(g, 'user') or g.user is None:
        return redirect(url_for('front.login'))
    return render_template('front/index.html', menu_items=[
        {'name': '首页', 'url': '/', 'icon': 'fa-home'},
        {'name': '图像检测', 'url': '/check/image', 'icon': 'fa-image'},
        {'name': '视频检测', 'url': '/check/video', 'icon': 'fa-video'},
        {'name': '地图', 'url': '/map', 'icon': 'fa-map-marker'},
        {'name': '关于', 'url': '/about', 'icon': 'fa-info-circle'}
    ])


@bp.route('/map')
@login_required
def map():
    return render_template('front/map.html')


# ---------------------------------------------------------------------------------------------------------- #
# 验证码相关
# ---------------------------------------------------------------------------------------------------------- #
@bp.route("/mail/captcha")
def mail_captcha():
    """发送邮箱验证码"""
    try:
        email = request.args.get("email")
        current_app.logger.info(f"收到邮箱验证码请求，邮箱: {email}")
        
        # 验证邮箱格式
        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            current_app.logger.warning(f"邮箱格式错误: {email}")
            return restful.params_error(message="邮箱格式错误")
        
        # 防止频繁发送
        if cache.get(f'email_cooldown_{email}'):
            current_app.logger.warning(f"邮箱请求过于频繁: {email}")
            return restful.params_error(message="操作过于频繁，请稍后再试")
            
        # 使用统一键名（此处直接使用email，确保删除与存储键一致）
        cache.delete(email)  # 删除旧验证码（无论是否存在）

        # 生成4位数字验证码（允许重复）
        digits = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
        captcha = ''.join(random.choices(digits, k=4))  # 使用random.choices允许重复
        current_app.logger.info(f"为邮箱 {email} 生成验证码: {captcha}")

        # 发送邮件
        current_app.logger.info(f"开始发送邮件到 {email}")
        subject = "【慧眼通途】验证码"
        body = f"【慧眼通途】您的验证码是：{captcha}，验证码有效期为5分钟，请勿告诉他人"
        
        # 使用Celery发送邮件
        from src.utils.bbs_celery import send_mail
        success = send_mail(email, subject, body)
        
        if not success:
            current_app.logger.error(f"向 {email} 发送邮件失败")
            return restful.server_error(message="邮件发送失败，请稍后再试")

        # 存储新验证码，有效期5分钟
        cache.set(email, captcha, timeout=60 * 5)
        # 添加冷却时间，防止频繁请求
        cache.set(f'email_cooldown_{email}', '1', timeout=60)  # 60秒冷却时间
        current_app.logger.info(f"向 {email} 发送邮件成功，验证码有效期5分钟")

        return restful.ok(message="验证码发送成功")
    except Exception as e:
        current_app.logger.error(f"发送邮箱验证码时发生异常: {str(e)}", exc_info=True)
        return restful.server_error(message="服务器内部错误！")


@bp.route("/sms/captcha")
def sms_captcha():
    """发送短信验证码"""
    try:
        phone = request.args.get("phone")
        current_app.logger.info(f"收到短信验证码请求，手机号: {phone}")
        
        # 验证手机格式
        if not re.match(r'^1[3-9]\d{9}$', phone):
            current_app.logger.warning(f"手机号格式错误: {phone}")
            return restful.params_error(message="手机号格式错误")

        # 防止频繁发送
        if cache.get(f'sms_cooldown_{phone}'):
            current_app.logger.warning(f"手机号请求过于频繁: {phone}")
            return restful.params_error(message="操作过于频繁，请稍后再试")

        # 生成4位数字验证码
        captcha = ''.join(random.choices('0123456789', k=4))
        current_app.logger.info(f"为手机 {phone} 生成验证码: {captcha}")

        # 调用短信服务商API发送短信
        current_app.logger.info(f"开始发送短信给 {phone}")
        success = send_sms(phone, captcha)
        
        if not success:
            current_app.logger.error(f"向 {phone} 发送短信失败")
            return restful.server_error(message="短信发送失败，请稍后再试")

        # 存储验证码（5分钟有效期）和冷却时间（60秒）
        cache.set(f'sms_{phone}', captcha, timeout=300)  # 5分钟有效期
        cache.set(f'sms_cooldown_{phone}', '1', timeout=60)  # 60秒冷却时间
        current_app.logger.info(f"向 {phone} 发送短信成功，验证码有效期5分钟")

        return restful.ok(message="短信发送成功")
    except Exception as e:
        current_app.logger.error(f"发送短信验证码时发生异常: {str(e)}", exc_info=True)
        return restful.server_error(message="服务器内部错误")


# ---------------------------------------------------------------------------------------------------------- #
# 用户认证相关
# ---------------------------------------------------------------------------------------------------------- #
@bp.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册"""
    if request.method == "GET":
        return render_template('front/register.html')
    else:
        register_type = request.form.get('register_type')
        
        if register_type == 'email':
            form = RegisterForm(request.form)
            if form.validate():
                email = form.email.data
                username = form.username.data
                password = form.password.data
                # 获取普通用户角色
                normal_user_role = RoleModel.query.filter_by(name='普通用户').first()
                # 创建用户
                user = UserModel(
                    email=email,
                    username=username,
                    password=password,
                    is_staff=False,
                    role=normal_user_role
                )
                db.session.add(user)
                db.session.commit()
                cache.delete(email)
                return redirect(url_for('front.login'))
            else:
                for message in form.messages:
                    flash(message)
                return redirect(url_for('front.register'))
        elif register_type == 'phone':
            form = PhoneRegisterForm(request.form)
            if form.validate():
                phone = form.phone.data
                username = form.username.data
                password = form.password.data
                # 获取普通用户角色
                normal_user_role = RoleModel.query.filter_by(name='普通用户').first()
                # 创建用户
                user = UserModel(
                    phone=phone,
                    username=username,
                    password=password,
                    is_staff=False,
                    phone_verified=True,
                    role=normal_user_role
                )
                db.session.add(user)
                db.session.commit()
                # 删除缓存中的验证码
                cache.delete(f'sms_{phone}')
                return redirect(url_for('front.login'))
            else:
                for message in form.messages:
                    flash(message)
                return redirect(url_for('front.register'))
        else:
            flash('无效的注册类型')
            return redirect(url_for('front.register'))


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录"""
    if request.method == "GET":
        return render_template('front/login.html')
    else:
        form = LoginForm(request.form)
        if form.validate():
            account = form.account.data
            password = form.password.data
            remember = form.remember.data
            
            user = None
            
            # 尝试邮箱登录
            if '@' in account:
                user = UserModel.query.filter_by(email=account).first()
            # 尝试手机号登录
            elif re.match(r'^1[3-9]\d{9}$', account):
                user = UserModel.query.filter_by(phone=account).first()
            # 尝试用户名登录
            else:
                user = UserModel.query.filter_by(username=account).first()
                
            if user and user.check_password(password):
                if not user.is_active:
                    flash("您的账号已被禁用！")
                    return redirect(url_for('front.login'))
                
                # 设置用户会话
                session['user_id'] = user.id
                
                # 如果用户选择了"7天内自动登录"，设置会话为永久性
                # Flask会根据PERMANENT_SESSION_LIFETIME设置实际过期时间（7天）
                if remember:
                    session.permanent = True
                
                # 记录最后登录时间
                user.last_login = datetime.now()
                db.session.commit()
                
                return redirect('/')
            else:
                flash("账号或密码错误！")
                return redirect(url_for('front.login'))
        else:
            for message in form.messages:
                flash(message)
            return redirect(url_for('front.login'))


@bp.get('/logout')
def logout():
    """用户退出登录"""
    session.pop('user_id', None)
    return redirect(url_for('front.login'))


@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """忘记密码"""
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        email = form.email.data
        user = UserModel.query.filter_by(email=email).first()

        if user:
            # 生成并存储重置令牌
            token = generate_reset_token(user.email)
            user.reset_token = token
            user.token_expiry = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()

            # 发送重置邮件（异步）
            reset_url = url_for('front.reset_password', token=token, _external=True)
            current_app.celery.send_task(
                'send_mail',
                (email, "密码重置通知",
                 f"请点击以下链接重置密码：{reset_url}\n若非本人操作请忽略")
            )

        # 统一提示避免邮箱探测
        flash("如果邮箱已注册，重置链接已发送至您的邮箱", "info")
        return redirect(url_for('front.login'))

    return render_template('front/forgot_password.html', form=form)


@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """重置密码"""
    user = verify_reset_token(token)
    if not user:
        flash("重置链接无效或已过期", "danger")
        return redirect(url_for('front.forgot_password'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.password = form.new_password.data  # 触发密码哈希
        user.reset_token = None  # 清除令牌
        db.session.commit()
        flash("密码重置成功，请重新登录", "success")
        return redirect(url_for('front.login'))

    return render_template('front/reset_password.html', form=form, token=token)


# ---------------------------------------------------------------------------------------------------------- #
# 用户信息相关
# ---------------------------------------------------------------------------------------------------------- #
@bp.get('/profile/<string:user_id>')
def profile(user_id):
    """用户个人中心"""
    user = UserModel.query.get(user_id)
    if not user:
        flash("用户不存在")
        return redirect(url_for('front.index'))
        
    is_mine = False
    if hasattr(g, "user") and g.user and g.user.id == user.id:
        is_mine = True
    
    # 获取当前时间，用于计算用户加入天数
    now = datetime.now()
    
    return render_template(
        'front/profile.html',
        user=user,
        is_mine=is_mine,
        now=now
    )


@bp.post('/profile/edit')
@login_required
def edit_profile():
    """编辑用户资料"""
    form = EditProfileForm(CombinedMultiDict([request.form, request.files]))
    # 检查是否为AJAX请求
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if form.validate():
        username = form.username.data
        avatar = form.avatar.data  # 上传的文件对象
        signature = form.signature.data
        success_message = None
        error_message = None

        if avatar:
            try:
                # 记录表单上传信息
                current_app.logger.info(f"接收到文件上传: {avatar.filename}, 大小: {len(avatar.read())}字节")
                # 重置文件指针
                avatar.seek(0)
                
                # 检查文件是否为空
                if avatar.filename == '':
                    current_app.logger.warning("上传的文件名为空")
                    flash("请选择有效的图片文件", "error")
                else:
                    # 从原始文件名中提取扩展名
                    original_filename = secure_filename(avatar.filename)
                    ext = ''
                    if '.' in original_filename:
                        ext = '.' + original_filename.rsplit('.', 1)[1].lower()
                    
                    # 生成简短的唯一文件名 (用户ID前8位 + 时间戳后4位 + 扩展名)
                    user_id_short = g.user.id[:8] if len(g.user.id) > 8 else g.user.id
                    timestamp = str(int(time.time()))
                    timestamp_short = timestamp[-4:] if len(timestamp) > 4 else timestamp
                    
                    # 最终的文件名格式: 8位用户ID_4位时间戳.扩展名
                    unique_filename = f"{user_id_short}_{timestamp_short}{ext}"
                    
                    current_app.logger.info(f"原始文件名: {original_filename}, 缩短后: {unique_filename}")
                    
                    # 检查并确保media目录存在
                    media_root = current_app.config['MEDIA_ROOT']
                    if not os.path.exists(media_root):
                        current_app.logger.info(f"创建媒体根目录: {media_root}")
                        os.makedirs(media_root, exist_ok=True)
                    
                    # 确保头像保存目录存在
                    avatars_dir = os.path.join(current_app.root_path, 'static', 'avatars')
                    current_app.logger.info(f"检查头像目录: {avatars_dir}")
                    if not os.path.exists(avatars_dir):
                        current_app.logger.info(f"创建头像目录: {avatars_dir}")
                        os.makedirs(avatars_dir, exist_ok=True)
                    
                    # 检查目录权限
                    try:
                        test_file = os.path.join(avatars_dir, 'test_write.tmp')
                        with open(test_file, 'w') as f:
                            f.write('test')
                        os.remove(test_file)
                        current_app.logger.info(f"目录 {avatars_dir} 有写入权限")
                    except Exception as e:
                        current_app.logger.error(f"目录 {avatars_dir} 无写入权限: {str(e)}")
                        flash(f"服务器存储权限错误，请联系管理员", "error")
                        return redirect(url_for('front.profile', user_id=g.user.id))
                    
                    # 保存文件
                    file_path = os.path.join(avatars_dir, unique_filename)
                    current_app.logger.info(f"保存头像至: {file_path}")
                    
                    # 确保路径分隔符统一为正斜杠
                    file_path_normalized = file_path.replace('\\', '/')
                    current_app.logger.info(f"规范化后路径: {file_path_normalized}")
                    
                    # 确保目录存在
                    save_dir = os.path.dirname(file_path)
                    os.makedirs(save_dir, exist_ok=True)
                    
                    # 保存文件
                    avatar.save(file_path)
                    
                    # 验证文件是否成功保存
                    if os.path.exists(file_path):
                        current_app.logger.info(f"文件保存成功: {file_path}, 大小: {os.path.getsize(file_path)}字节")
                        
                        # 更新用户头像URL，标准化路径格式
                        # 添加时间戳防止浏览器缓存
                        timestamp = int(time.time())
                        
                        # 确保使用正斜杠作为路径分隔符
                        safe_filename = unique_filename.replace('\\', '/')
                        
                        # 简化的头像URL，只保留必要部分
                        avatar_url = f"avatars/{safe_filename}"
                        
                        # 生成URL路径，使用静态文件路径
                        avatar_path = url_for('static', filename=avatar_url, _external=False)
                        
                        # 计算URL长度，确保不超过数据库字段限制
                        max_length = 98  # 留2个字符作为余量
                        if len(avatar_path) > max_length:
                            # 如果路径太长，则截断并记录警告
                            current_app.logger.warning(f"头像URL路径过长({len(avatar_path)}字符)，将被截断")
                            avatar_path = avatar_path[:max_length]
                            
                        # 添加时间戳查询参数（确保总长度仍在限制内）
                        if '?' in avatar_path:
                            avatar_path = f"{avatar_path}&t={timestamp_short}"
                        else:
                            avatar_path = f"{avatar_path}?t={timestamp_short}"
                            
                        # 再次检查长度
                        if len(avatar_path) > 100:
                            # 最后的安全检查
                            avatar_path = avatar_path[:100]
                            
                        g.user.avatar = avatar_path
                        current_app.logger.info(f"更新用户头像URL: {g.user.avatar} (长度: {len(g.user.avatar)}字符)")
                        
                        # 设置标志
                        session['avatar_updated'] = True
                        flash("头像更新成功！", "success")
                        success_message = "头像更新成功！"
                    else:
                        current_app.logger.error(f"文件保存失败: {file_path}")
                        flash("头像保存失败，请重试", "error")
                        error_message = "头像保存失败，请重试"
            except Exception as e:
                current_app.logger.error(f"头像上传失败: {str(e)}")
                flash(f"头像上传失败: {str(e)}", "error")
                error_message = f"头像上传失败: {str(e)}"

        g.user.username = username
        g.user.signature = signature
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()  # 回滚事务
            
            # 处理特定类型的数据库错误
            error_message = "保存资料时发生错误，请稍后重试"
            
            # 记录详细错误信息以便调试
            current_app.logger.error(f"数据库错误: {str(e)}")
            
            # 检查是否是数据长度错误
            if "Data too long" in str(e):
                error_message = "头像URL过长，请选择较短文件名的图片"
                current_app.logger.error(f"头像URL过长: {g.user.avatar}")
                
            flash(error_message, "error")
            
            # 如果是AJAX请求，返回JSON响应
            if is_ajax:
                return jsonify({"error": error_message}), 400
                
            return redirect(url_for('front.profile', user_id=g.user.id))
        
        # 如果是AJAX请求，返回JSON响应
        if is_ajax:
            response_data = {"success": True}
            if success_message:
                response_data["message"] = success_message
            return jsonify(response_data)
        
        # 创建带有缓存控制的响应
        redirect_url = url_for('front.profile', user_id=g.user.id, t=int(time.time()))
        
        # 添加成功或错误消息参数
        if 'success_message' in locals() and success_message:
            redirect_url = f"{redirect_url}&success={quote(success_message)}"
        elif 'error_message' in locals() and error_message:
            redirect_url = f"{redirect_url}&error={quote(error_message)}"
            
        response = redirect(redirect_url)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    else:
        # 如果表单验证失败
        error_messages = []
        for field, errors in form.errors.items():
            for error in errors:
                error_messages.append(f"{field}: {error}")
                flash(f"{field}: {error}")
        
        # 如果是AJAX请求，返回错误响应
        if is_ajax:
            return jsonify({"error": error_messages[0] if error_messages else "表单验证失败"}), 400
            
        return redirect(url_for('front.profile', user_id=g.user.id))


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    """修改密码"""
    form = ChangePasswordForm()  # 直接实例化表单
    if request.method == "POST":
        if form.validate_on_submit():  # 自动验证 CSRF
            user = g.user
            user.password = form.new_password.data  # 触发密码哈希
            db.session.commit()
            flash("密码修改成功，请重新登录", "success")
            session.pop("user_id", None)
            return redirect(url_for("front.login"))
        else:
            for error in form.errors.values():
                flash(error[0])
    # GET 请求或验证失败时渲染模板
    return render_template("front/change_password.html", form=form)


# ---------------------------------------------------------------------------------------------------------- #
# 内容相关API
# ---------------------------------------------------------------------------------------------------------- #
@bp.route('/api/banners')
def get_banners():
    """获取轮播图列表"""
    banners = BannerModel.query.filter_by(status=1).order_by(BannerModel.sort_order.asc()).all()
    result = []
    for banner in banners:
        result.append({
            'id': banner.id,
            'title': banner.title,
            'image_url': banner.image_url,
            'link_url': banner.link_url
        })
    return jsonify({'code': 200, 'message': '获取成功', 'data': result})


@bp.route('/api/notices')
def get_notices():
    """获取公告列表"""
    # 只获取状态为启用的公告
    notices = NoticeModel.query.filter_by(status=1)
    
    # 检查是否需要只获取重要公告
    important_only = request.args.get('important', '0') == '1'
    if important_only:
        notices = notices.filter_by(is_important=1)
        
    # 检查是否有结束时间的限制：只获取有效期内的或没有设置结束时间的
    current_time = datetime.now()
    notices = notices.filter(
        (NoticeModel.end_time.is_(None)) | (NoticeModel.end_time >= current_time)
    )
    
    # 按发布时间倒序排序
    notices = notices.order_by(NoticeModel.publish_time.desc())
    
    # 支持分页
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    pagination = notices.paginate(page=page, per_page=per_page)
    
    result = []
    for notice in pagination.items:
        result.append({
            'id': notice.id,
            'title': notice.title,
            'content': notice.content,
            'publish_time': notice.publish_time.strftime('%Y-%m-%d %H:%M:%S'),
            'end_time': notice.end_time.strftime('%Y-%m-%d %H:%M:%S') if notice.end_time else None,
            'is_important': bool(notice.is_important)
        })
    
    return jsonify({
        'code': 200, 
        'message': '获取成功', 
        'data': {
            'items': result,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': pagination.page
        }
    })


@bp.route('/api/notices/<int:notice_id>')
def get_notice_detail(notice_id):
    """获取公告详情"""
    notice = NoticeModel.query.get_or_404(notice_id)
    
    # 检查公告是否有效
    if notice.status != 1:
        abort(404)
        
    # 检查公告是否在有效期内
    current_time = datetime.now()
    if notice.end_time and notice.end_time < current_time:
        abort(404)
    
    # 记录访问日志
    log_content_access(notice_id, 'notice')
        
    result = {
        'id': notice.id,
        'title': notice.title,
        'content': notice.content,
        'publish_time': notice.publish_time.strftime('%Y-%m-%d %H:%M:%S'),
        'end_time': notice.end_time.strftime('%Y-%m-%d %H:%M:%S') if notice.end_time else None,
        'is_important': bool(notice.is_important)
    }
    
    return jsonify({'code': 200, 'message': '获取成功', 'data': result})


# ---------------------------------------------------------------------------------------------------------- #
# 系统相关
# ---------------------------------------------------------------------------------------------------------- #
@bp.route('/timeline/uptime')
def uptime():
    """获取系统运行时间"""
    now = datetime.now()
    uptime = now - start_time

    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    return jsonify({
        "days": days,
        "hours": hours,
        "minutes": minutes,
    })


@bp.route('/.well-known/acme-challenge/<filename>')
def serve_static_validation(filename):
    """SSL证书验证"""
    return bp.send_static_file(f'.well-known/acme-challenge/{filename}')
