from datetime import datetime, timedelta

from flask import Blueprint, jsonify
from flask import render_template
from flask import redirect
from flask import g
from ..common.models import PermissionEnum
from ..front.models import UserModel, UserLogModel, VehicleAppointmentModel, BannerModel, NoticeModel
from src.utils.decorators import permission_required, login_required
from flask import request
from .forms import (
    AddStaffForm, EditStaffForm, VehicleAppointmentApprovalForm, BannerForm, NoticeForm
)
from flask import flash
from flask import url_for
from src.utils.exts import db, cache, avatars
from .models import RoleModel, ContentAccessLog, PermissionModel
from src.utils import restful
# from apscheduler.schedulers.background import BackgroundScheduler
# from src.utils.exts import socketio
import random
from datetime import datetime, timedelta
from flask import session
import json
import os
from werkzeug.utils import secure_filename
from flask import current_app
from flask_avatars import Identicon
from werkzeug.security import generate_password_hash
from sqlalchemy import func, desc, or_
from functools import wraps
import uuid
import time
import shutil
import re
import logging
from flask import send_from_directory, abort
from flask_paginate import Pagination
from ..common.captcha import Captcha
from sqlalchemy import asc, desc
from src.blueprints.common.forms import CSRFTokenForm
from src.utils.random_token import generate_token
from ..front.models import LogModel
from src.blueprints.front.forms import RegisterForm, LoginForm
import math
import string
import mimetypes
from werkzeug.utils import secure_filename
from flask import send_file




bp = Blueprint('cms', __name__, url_prefix='/cms')

# ================================= 管理员首页 ================================= #
@bp.route('/')
@login_required
@permission_required(PermissionEnum.VIEW_STATS)
def index():
    # 获取用户总数
    total_users = UserModel.query.count()

    # 计算今日新增（UTC时间）
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)
    today_new = UserModel.query.filter(
        UserModel.join_time >= today_start
    ).count()
    
    # 获取预约状态统计
    pending_count = VehicleAppointmentModel.query.filter_by(status='待审核').count()
    approved_count = VehicleAppointmentModel.query.filter_by(status='已通过').count()
    rejected_count = VehicleAppointmentModel.query.filter_by(status='已拒绝').count()

    # 获取总访问量统计
    try:
        total_visits = ContentAccessLog.query.count()
    except Exception as e:
        print(f"获取访问量数据出错: {str(e)}")
        total_visits = 0
        
    # 获取系统状态信息
    system_status = get_system_status()

    return render_template(
        'cms/index.html',
        total_users=total_users,
        today_new_users=today_new,
        pending_count=pending_count,
        approved_count=approved_count,
        rejected_count=rejected_count,
        total_visits=total_visits,
        **system_status
    )

def get_system_status():
    """获取系统状态信息"""
    import psutil
    import time
    import redis
    import paho.mqtt.client as mqtt
    from sqlalchemy import text
    from flask import current_app
    
    try:
        # 1. 服务器负载信息
        cpu_percent = psutil.cpu_percent(interval=0.5)
        
        # 2. 数据库状态
        try:
            # 执行简单查询检查数据库连接
            db.session.execute(text('SELECT 1'))
            db_status = "运行正常"
            db_status_class = "success"
        except Exception as e:
            db_status = f"异常: {str(e)}"
            db_status_class = "danger"
        
        # 3. MQTT服务状态
        mqtt_status = "未连接"
        mqtt_status_class = "danger"
        mqtt_percent = 0
        
        try:
            # 创建MQTT客户端
            mqtt_client = mqtt.Client(client_id="mqtt_status_checker")
            # MQTT连接参数，从配置文件或环境变量获取
            mqtt_broker = "8.138.192.81"  # 使用从YOLO项目中找到的MQTT服务器地址
            mqtt_port = 1883
            
            # 设置连接超时
            mqtt_client.connect_async(mqtt_broker, mqtt_port, 60)
            mqtt_client.loop_start()
            
            # 等待连接响应
            time.sleep(1)
            
            # 检查连接状态
            if mqtt_client.is_connected():
                mqtt_status = "已连接"
                mqtt_status_class = "success"
                mqtt_percent = 100
            else:
                mqtt_status = "连接失败"
                mqtt_status_class = "warning"
                mqtt_percent = 30
                
            # 断开连接
            mqtt_client.disconnect()
            mqtt_client.loop_stop()
            
        except Exception as e:
            mqtt_status = f"异常: {str(e)[:50]}"
            mqtt_status_class = "danger"
            mqtt_percent = 0
        
        # 4. Redis服务状态
        redis_status = "未连接"
        redis_status_class = "danger"
        redis_percent = 0
        
        try:
            # 从应用配置获取Redis连接信息
            redis_host = current_app.config.get('CACHE_REDIS_HOST', '117.72.120.52')
            redis_port = current_app.config.get('CACHE_REDIS_PORT', 6379)
            redis_password = current_app.config.get('CACHE_REDIS_PASSWORD', 'redispasswd')
            
            # 创建Redis客户端并检查连接
            redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password,
                socket_timeout=2
            )
            
            # 执行简单命令检查连接
            ping_result = redis_client.ping()
            if ping_result:
                redis_status = "运行正常"
                redis_status_class = "success"
                redis_percent = 100
                
                # 获取Redis占用内存信息
                info = redis_client.info()
                redis_memory_used = info.get('used_memory_human', 'Unknown')
                redis_status = f"运行正常 ({redis_memory_used})"
            else:
                redis_status = "已连接但异常"
                redis_status_class = "warning"
                redis_percent = 50
                
        except Exception as e:
            redis_status = f"异常: {str(e)[:50]}"
            redis_status_class = "danger"
            redis_percent = 0
        
        # 5. 系统运行时间
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        days = int(uptime_seconds // (24 * 3600))
        hours = int((uptime_seconds % (24 * 3600)) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        uptime = f"{days}天 {hours}小时 {minutes}分钟"
        
        return {
            'cpu_percent': cpu_percent,
            'db_status': db_status,
            'db_status_class': db_status_class,
            'mqtt_status': mqtt_status,
            'mqtt_status_class': mqtt_status_class,
            'mqtt_percent': mqtt_percent,
            'redis_status': redis_status,
            'redis_status_class': redis_status_class,
            'redis_percent': redis_percent,
            'system_uptime': uptime
        }
    except Exception as e:
        print(f"获取系统状态出错: {str(e)}")
        # 返回默认值
        return {
            'cpu_percent': 65,
            'db_status': "未知",
            'db_status_class': "warning",
            'mqtt_status': "未知",
            'mqtt_status_class': "warning",
            'mqtt_percent': 0,
            'redis_status': "未知",
            'redis_status_class': "warning",
            'redis_percent': 0,
            'system_uptime': "未知"
        }

# ================================= 用户增长数据API ================================= #
@bp.route('/api/user-growth')
@login_required
@permission_required(PermissionEnum.VIEW_STATS)
def user_growth_data():
    # 获取过去30天的数据
    days = request.args.get('days', 30, type=int)
    if days > 365:  # 限制最大查询天数
        days = 365
    
    end_date = datetime.utcnow().replace(hour=23, minute=59, second=59)
    start_date = (end_date - timedelta(days=days)).replace(hour=0, minute=0, second=0)
    
    # 准备数据结构
    date_labels = []
    new_users_data = []
    cumulative_users_data = []
    
    # 获取起始日期前的总用户数作为基数
    base_count = UserModel.query.filter(UserModel.join_time < start_date).count()
    cumulative_count = base_count
    
    # 按天统计数据
    current_date = start_date
    while current_date <= end_date:
        next_date = current_date + timedelta(days=1)
        
        # 当天新增用户
        daily_new_users = UserModel.query.filter(
            UserModel.join_time >= current_date,
            UserModel.join_time < next_date
        ).count()
        
        # 更新累计用户
        cumulative_count += daily_new_users
        
        # 格式化日期为"MM-DD"格式
        formatted_date = current_date.strftime('%m-%d')
        
        # 添加到结果列表
        date_labels.append(formatted_date)
        new_users_data.append(daily_new_users)
        cumulative_users_data.append(cumulative_count)
        
        # 移到下一天
        current_date = next_date
    
    # 返回JSON格式数据
    return jsonify({
        'labels': date_labels,
        'newUsers': new_users_data,
        'cumulativeUsers': cumulative_users_data
    })

# ================================= 内容访问量热力图API ================================= #
@bp.route('/api/content-access-heatmap')
@login_required
@permission_required(PermissionEnum.VIEW_STATS)
def content_access_heatmap():
    # 获取过去N天的数据
    days = request.args.get('days', 30, type=int)
    if days > 365:  # 限制最大查询天数
        days = 365
    
    end_date = datetime.utcnow().replace(hour=23, minute=59, second=59)
    start_date = (end_date - timedelta(days=days)).replace(hour=0, minute=0, second=0)
    
    # 准备热力图数据结构 
    # 按小时统计的二维数组 [日期][小时] = 访问量
    # 索引0是周一，索引6是周日
    weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    hour_labels = [f"{h}时" for h in range(24)]
    
    # 初始化热力图数据
    heatmap_data = [[0 for _ in range(24)] for _ in range(7)]
    
    try:
        # 查询时间范围内的访问记录
        access_logs = ContentAccessLog.query.filter(
            ContentAccessLog.access_time >= start_date,
            ContentAccessLog.access_time <= end_date
        ).all()
        
        # 统计每个时间段的访问量
        for log in access_logs:
            weekday = log.access_time.weekday()  # 0-6，0表示周一
            hour = log.access_time.hour  # 0-23
            heatmap_data[weekday][hour] += 1
        
        # 统计每种内容类型的访问量
        content_types = db.session.query(
            ContentAccessLog.content_type,
            db.func.count(ContentAccessLog.id)
        ).filter(
            ContentAccessLog.access_time >= start_date,
            ContentAccessLog.access_time <= end_date
        ).group_by(ContentAccessLog.content_type).all()
        
        content_type_data = {
            "labels": [item[0] for item in content_types],
            "values": [item[1] for item in content_types]
        }
    except Exception as e:
        # 如果表不存在或发生其他错误，使用模拟数据
        print(f"访问量热力图数据查询出错: {str(e)}")
        
        # 生成一些随机的模拟数据用于展示
        import random
        for day in range(7):
            for hour in range(24):
                # 工作日工作时间访问量较高
                if day < 5 and 9 <= hour <= 18:
                    heatmap_data[day][hour] = random.randint(10, 30)
                # 晚间时段
                elif 19 <= hour <= 23:
                    heatmap_data[day][hour] = random.randint(5, 15)
                # 其他时间段访问量较低
                else:
                    heatmap_data[day][hour] = random.randint(0, 5)
        
        # 模拟内容类型数据
        content_type_data = {
            "labels": ["notice", "article", "news"],
            "values": [random.randint(30, 100), random.randint(20, 80), random.randint(10, 50)]
        }
    
    # 返回JSON格式数据
    return jsonify({
        'weekdayLabels': weekday_names,
        'hourLabels': hour_labels,
        'heatmapData': heatmap_data,
        'contentTypeData': content_type_data
    })

# 钩子函数
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
    
    # 获取当前请求的终点
    endpoint = request.endpoint
    
    # 如果是CMS蓝图的路由，需要检查用户权限
    if endpoint and endpoint.startswith('cms.'):
        # 对于媒体库相关的路由，我们会通过permission_required装饰器检查权限
        # 这些路由不需要在这里检查is_staff
        if endpoint in ['cms.get_media_files', 
                       'cms.upload_media_files', 'cms.create_media_folder', 
                       'cms.delete_media_item']:
            # 只检查用户是否存在，存在则允许继续（具体权限由装饰器检查）
            if not hasattr(g, 'user') or g.user is None:
                return redirect(url_for('front.login'))
        else:
            # 确保当前请求的上下文（g）中有user属性且user不为None，并且g.user.is_staff为True，否则重定向到首页
            if not hasattr(g, 'user') or g.user is None or g.user.is_staff != True:
                return redirect('/')

# 上下文处理器
@bp.context_processor
def cms_context_processor():
    # 定义一个 cms_context_processor() 函数，用于将 PermissionEnum 枚举类添加到模板上下文中
    return {"PermissionEnum": PermissionEnum}

# ========================================= 用户列表 ========================================== #
@bp.get("/staff/list")
@permission_required(PermissionEnum.CMS_USER)
def staff_list():
    # 获取页码和搜索参数
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    # 获取所有非超级管理员的角色
    roles = RoleModel.query.filter(RoleModel.name != '超级管理员').all()
    
    # 构建查询，获取所有非普通用户角色的用户
    query = UserModel.query.join(RoleModel).filter(
        RoleModel.name != '普通用户'
    )
    
    # 如果有搜索条件，添加搜索过滤
    if search:
        query = query.filter(
            db.or_(
                UserModel.username.ilike(f'%{search}%'),
                UserModel.email.ilike(f'%{search}%'),
                UserModel.phone.ilike(f'%{search}%')
            )
        )
    
    # 分页
    pagination = query.paginate(
        page=page,
        per_page=10,
        error_out=False
    )
    
    return render_template(
        "cms/staff_list.html", 
        users=pagination.items, 
        pagination=pagination,
        all_roles=roles,
        search=search,
        current_page=page,
        total_pages=pagination.pages
    )

# ========================================= 添加用户 ========================================== #
@bp.route("/staff/add", methods=['GET', 'POST'])
@permission_required(PermissionEnum.CMS_USER)
def add_staff():
    if request.method == "GET":
        # 只获取非超级管理员的角色
        roles = RoleModel.query.filter(RoleModel.name.notin_(['超级管理员', '普通用户'])).all()
        return render_template("cms/add_staff.html", roles=roles)
    else:
        # 获取表单数据
        username = request.form.get('username')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        role_id = request.form.get('role_id')
        
        # 验证必填字段
        if not all([username, email, password, password_confirm, role_id]):
            flash("请填写所有必填字段", "danger")
            return redirect(url_for("cms.add_staff"))
        
        # 验证密码匹配
        if password != password_confirm:
            flash("两次输入的密码不一致", "danger")
            return redirect(url_for("cms.add_staff"))
        
        # 验证角色是否为超级管理员
        role = RoleModel.query.get(role_id)
        if not role:
            flash("所选角色不存在", "danger")
            return redirect(url_for("cms.add_staff"))
            
        if role.name == '超级管理员':
            flash("不能添加超级管理员用户", "danger")
            return redirect(url_for("cms.add_staff"))
        
        # 检查用户是否已存在
        existing_user = UserModel.query.filter(
            db.or_(
                UserModel.email == email,
                UserModel.username == username
            )
        ).first()
        
        if existing_user:
            flash("用户名或邮箱已被使用", "danger")
            return redirect(url_for("cms.add_staff"))
        
        # 创建新用户
        try:
            user = UserModel(
                username=username,
                email=email,
                phone=phone,
                password=password,
                role_id=role_id,
                is_staff=True
            )
            db.session.add(user)
            db.session.commit()
            
            flash("员工添加成功", "success")
            return redirect(url_for("cms.staff_list"))
        except Exception as e:
            db.session.rollback()
            flash(f"添加失败: {str(e)}", "danger")
            return redirect(url_for("cms.add_staff"))

# =============================================== 编辑用户 ================================= #
@bp.route("/staff/edit/<string:user_id>", methods=['GET', 'POST'])
@permission_required(PermissionEnum.CMS_USER)
def edit_staff(user_id):
    user = UserModel.query.get_or_404(user_id)
    roles = RoleModel.query.all()

    # 统一处理GET/POST请求的选项设置
    if request.method == "GET":
        form = EditStaffForm(obj=user)
    else:
        form = EditStaffForm(request.form)

    # 关键修复：设置角色选项
    form.role.choices = [(role.id, role.name) for role in roles]

    if request.method == "POST" and form.validate():
        try:
            # 邮箱唯一性验证（排除当前用户）
            if UserModel.query.filter(
                    UserModel.email == form.email.data,
                    UserModel.id != user.id
            ).first():
                flash("该邮箱已被其他用户使用", "danger")
                return redirect(url_for('cms.edit_staff', user_id=user_id))
            # 更新用户信息
                # 如果用户是普通用户，确保 is_staff 为 False
            if user.role.name == '普通用户':
                user.is_staff = False
            else:# 不是普通用户，执行下面操作
                user.username = form.username.data
                user.email = form.email.data
                user.is_staff = form.is_staff.data
                user.role_id = form.role.data

            db.session.commit()
            flash("用户信息更新成功", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"更新失败: {str(e)}", "danger")

        return redirect(url_for('cms.staff_list', user_id=user_id))

    # 表单验证失败处理
    for field, errors in form.errors.items():
        for error in errors:
            flash(f"{field}: {error}", "danger")
    return render_template("cms/edit_staff.html",user=user,form=form,roles=roles)

# ========================================= 管理前台用户 ========================================== #
@bp.route("/users")
@permission_required(PermissionEnum.FRONT_USER)
def users_list():
    # 获取请求参数
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()

    # 获取普通用户角色
    normal_user_role = RoleModel.query.filter_by(name='普通用户').first()
    if not normal_user_role:
        return restful.params_error(message="普通用户角色不存在")

    # 构建基础查询 - 只查询普通用户角色的用户
    query = UserModel.query.filter_by(role_id=normal_user_role.id)

    # 添加搜索条件
    if search:
        search_pattern = f'%{search}%'
        query = query.filter(
            db.or_(
                UserModel.username.ilike(search_pattern),
                UserModel.email.ilike(search_pattern),
                UserModel.phone.ilike(search_pattern)
            )
        )

    # 执行分页查询
    per_page = 10  # 每页显示数量
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # 获取所有非超级管理员角色
    roles = RoleModel.query.filter(RoleModel.name != '超级管理员').all()

    return render_template(
        "cms/front_users.html",
        users=pagination.items,
        pagination=pagination,
        search=search,
        all_roles=roles
    )

@bp.post("front/users/<string:user_id>")
@permission_required(PermissionEnum.FRONT_USER)
def active_user(user_id):
    is_active = request.form.get("is_active", type=int)
    if is_active is None:
        return restful.params_error(message="请传入is_active参数")
    user = UserModel.query.get(user_id)
    if not user:
        return restful.params_error(message="用户不存在")
    # user = UserModel.query.get(user_id)
    user.is_active = bool(is_active)

    db.session.commit()
    return restful.ok(message="用户状态更新成功")

@bp.post("/front/users/<string:user_id>/update-role")
@permission_required(PermissionEnum.FRONT_USER)
def update_front_user_role(user_id):
    """更新前台用户角色API"""
    user = UserModel.query.get(user_id)
    if not user:
        return restful.params_error(message="用户不存在")
    
    role_id = request.form.get('role_id', type=int)
    if not role_id:
        return restful.params_error(message="请选择角色")
    
    role = RoleModel.query.get(role_id)
    if not role:
        return restful.params_error(message="角色不存在")
    
    # 检查是否尝试将用户设置为超级管理员
    if role.name == '超级管理员':
        return restful.params_error(message="不能将用户设置为超级管理员")
    
    # 更新用户角色
    user.role = role
    
    # 根据角色更新is_staff状态
    if role.name == '普通用户':
        user.is_staff = False
    else:
        user.is_staff = True
    
    db.session.commit()
    
    # 记录操作日志
    if hasattr(g, 'user') and g.user:
        log = UserLogModel(
            user_id=g.user.id,
            action="修改前台用户权限",
            ip_address=request.remote_addr,
            device_info=request.user_agent.string,
            details=f"修改前台用户 {user.username}({user.id}) 的角色为 {role.name}"
        )
        db.session.add(log)
        db.session.commit()
    
    return restful.ok(message="用户角色更新成功")

# ----------------------------用户增长-----------------------#
# --------------------------------------------------------#

# ========================================= 日志管理 ========================================== #
@bp.route("/logs")
@permission_required(PermissionEnum.LOGS)
def logs_list():
    """用户日志列表页面"""
    # 获取筛选参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    user_id = request.args.get('user_id', '')
    action = request.args.get('action', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    # 构建查询
    query = UserLogModel.query
    
    # 应用筛选条件
    if user_id:
        query = query.filter(UserLogModel.user_id == user_id)
    
    if action:
        query = query.filter(UserLogModel.action == action)
    
    if start_date:
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').replace(hour=0, minute=0, second=0)
        query = query.filter(UserLogModel.create_time >= start_date_obj)
    
    if end_date:
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        query = query.filter(UserLogModel.create_time <= end_date_obj)
    
    # 按时间倒序排序
    query = query.order_by(UserLogModel.create_time.desc())
    
    # 分页
    pagination = query.paginate(page=page, per_page=per_page)
    logs = pagination.items
    
    # 获取所有用户，用于筛选
    users = UserModel.query.all()
    
    # 获取所有操作类型
    action_types = db.session.query(UserLogModel.action).distinct().all()
    action_types = [action[0] for action in action_types]
    
    return render_template(
        'cms/logs_list.html', 
        logs=logs, 
        pagination=pagination,
        users=users,
        action_types=action_types,
        current_user_id=user_id,
        current_action=action,
        current_start_date=start_date,
        current_end_date=end_date
    )

@bp.route("/logs/<int:log_id>")
@permission_required(PermissionEnum.LOGS)
def log_detail(log_id):
    """日志详情页面"""
    log = UserLogModel.query.get_or_404(log_id)
    
    # 解析详情字段（如果有）
    log_details = None
    log_details_formatted = ""
    
    if log.details:
        try:
            log_details = json.loads(log.details)
            log_details_formatted = json.dumps(log_details, indent=4, ensure_ascii=False)
        except:
            log_details_formatted = log.details
    
    return render_template('cms/log_detail.html', log=log, log_details=log_details, log_details_formatted=log_details_formatted)

@bp.route("/logs/delete/<int:log_id>", methods=["POST"])
@permission_required(PermissionEnum.LOGS)
def delete_log(log_id):
    """删除单条日志"""
    log = UserLogModel.query.get_or_404(log_id)
    
    db.session.delete(log)
    db.session.commit()
    
    flash("日志记录已成功删除", "success")
    return redirect(url_for('cms.logs_list'))

@bp.route("/logs/clear", methods=["POST"])
@permission_required(PermissionEnum.LOGS)
def clear_logs():
    """清除符合条件的日志"""
    days = request.form.get('days', type=int)
    user_id = request.form.get('user_id', '')
    action = request.form.get('action', '')
    
    if not days:
        flash("请指定要清除的日志时间范围", "error")
        return redirect(url_for('cms.logs_list'))
    
    # 构建删除查询
    delete_before = datetime.now() - timedelta(days=days)
    
    # 先获取要删除的记录数量
    query = UserLogModel.query.filter(UserLogModel.create_time < delete_before)
    
    if user_id:
        query = query.filter(UserLogModel.user_id == user_id)
    
    if action:
        query = query.filter(UserLogModel.action == action)
    
    # 计算删除的记录数
    count = query.count()
    
    # 执行删除
    query.delete()
    db.session.commit()
    
    flash(f"成功清除了 {count} 条日志记录", "success")
    return redirect(url_for('cms.logs_list'))

# ========================================= 车辆预约管理 ========================================== #
@bp.route("/vehicle-appointments")
@permission_required(PermissionEnum.VEHICLE_APPOINTMENT)
def vehicle_appointments_list():
    # 获取筛选参数
    status = request.args.get('status', '')
    license_plate = request.args.get('license_plate', '')
    phone = request.args.get('phone', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    # 创建查询对象
    query = VehicleAppointmentModel.query
    
    # 应用筛选条件
    if status:
        query = query.filter(VehicleAppointmentModel.status == status)
    if license_plate:
        query = query.filter(VehicleAppointmentModel.license_plate.like(f'%{license_plate}%'))
    if phone:
        query = query.filter(VehicleAppointmentModel.phone.like(f'%{phone}%'))
    if start_date:
        start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
        query = query.filter(VehicleAppointmentModel.appointment_date >= start_datetime)
    if end_date:
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
        end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
        query = query.filter(VehicleAppointmentModel.appointment_date <= end_datetime)
    
    # 分页
    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(VehicleAppointmentModel.create_time.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    
    appointments = pagination.items
    
    # 获取状态计数
    pending_count = VehicleAppointmentModel.query.filter_by(status='待审核').count()
    approved_count = VehicleAppointmentModel.query.filter_by(status='已通过').count()
    rejected_count = VehicleAppointmentModel.query.filter_by(status='已拒绝').count()
    
    # 渲染模板
    return render_template(
        'cms/vehicle_appointments.html',
        appointments=appointments,
        pagination=pagination,
        status=status,
        license_plate=license_plate,
        phone=phone,
        start_date=start_date,
        end_date=end_date,
        pending_count=pending_count,
        approved_count=approved_count,
        rejected_count=rejected_count
    )

@bp.route("/vehicle-appointments/<int:appointment_id>", methods=['GET', 'POST'])
@permission_required(PermissionEnum.VEHICLE_APPOINTMENT)
def vehicle_appointment_detail(appointment_id):
    # 获取预约记录
    appointment = VehicleAppointmentModel.query.get_or_404(appointment_id)
    
    # 处理表单提交
    if request.method == 'POST':
        form = VehicleAppointmentApprovalForm(request.form)
        if form.validate():
            appointment.status = form.status.data
            
            # 如果有备注，可以添加到一个新的字段或通过其他方式保存
            # 这里假设添加了一个新字段来保存备注
            if hasattr(appointment, 'comment') and form.comment.data:
                appointment.comment = form.comment.data
            
            # 记录操作日志
            log = UserLogModel(
                user_id=g.user.id,
                action='审批车辆预约',
                ip_address=request.remote_addr,
                details=json.dumps({
                    'appointment_id': appointment.id,
                    'status': appointment.status,
                    'comment': form.comment.data if form.comment.data else ''
                })
            )
            
            db.session.add(log)
            db.session.commit()
            
            flash(f'预约审批已更新为: {appointment.status}', 'success')
            return redirect(url_for('cms.vehicle_appointments_list'))
        else:
            for message in form.messages:
                flash(message, 'danger')
    
    # GET请求，准备表单
    form = VehicleAppointmentApprovalForm()
    if appointment.status != '待审核':
        form.status.data = appointment.status
    
    # 查找关联用户
    user = None
    if appointment.user_id:
        user = UserModel.query.get(appointment.user_id)
    
    return render_template(
        'cms/vehicle_appointment_detail.html',
        appointment=appointment,
        form=form,
        user=user
    )

@bp.route("/vehicle-appointments/batch-approve", methods=['POST'])
@permission_required(PermissionEnum.VEHICLE_APPOINTMENT)
def vehicle_appointment_batch_approve():
    # 获取选中的预约ID列表
    appointment_ids = request.form.getlist('appointment_ids')
    
    if not appointment_ids:
        flash('请选择要批量审批的预约', 'warning')
        return redirect(url_for('cms.vehicle_appointments_list'))
    
    # 获取目标状态
    status = request.form.get('status')
    if status not in ['已通过', '已拒绝']:
        flash('无效的审批状态', 'danger')
        return redirect(url_for('cms.vehicle_appointments_list'))
    
    try:
        # 更新所有选中的预约状态
        appointments = VehicleAppointmentModel.query.filter(
            VehicleAppointmentModel.id.in_(appointment_ids)
        ).all()
        
        for appointment in appointments:
            appointment.status = status
            
            # 记录操作日志
            log = UserLogModel(
                user_id=g.user.id,
                action='批量审批车辆预约',
                ip_address=request.remote_addr,
                details=json.dumps({
                    'appointment_id': appointment.id,
                    'status': status
                })
            )
            db.session.add(log)
        
        db.session.commit()
        flash(f'已批量{status}了 {len(appointments)} 条预约', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'批量审批失败: {str(e)}', 'danger')
    
    return redirect(url_for('cms.vehicle_appointments_list'))

@bp.route("/vehicle-appointments/delete/<int:appointment_id>", methods=['POST'])
@permission_required(PermissionEnum.VEHICLE_APPOINTMENT)
def vehicle_appointment_delete(appointment_id):
    """删除预约信息"""
    try:
        # 获取预约记录
        appointment = VehicleAppointmentModel.query.get_or_404(appointment_id)
        
        # 记录操作日志
        log = UserLogModel(
            user_id=g.user.id,
            action='删除车辆预约',
            ip_address=request.remote_addr,
            details=json.dumps({
                'appointment_id': appointment.id,
                'license_plate': appointment.license_plate,
                'name': appointment.name,
                'phone': appointment.phone,
                'status': appointment.status
            })
        )
        db.session.add(log)
        
        # 删除预约
        db.session.delete(appointment)
        db.session.commit()
        
        flash('预约信息已成功删除', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'删除失败: {str(e)}', 'danger')
    
    return redirect(url_for('cms.vehicle_appointments_list'))

@bp.route("/vehicle-appointments/batch-delete", methods=['POST'])
@permission_required(PermissionEnum.VEHICLE_APPOINTMENT)
def vehicle_appointment_batch_delete():
    """批量删除预约信息"""
    # 获取选中的预约ID列表
    appointment_ids = request.form.getlist('appointment_ids')
    
    if not appointment_ids:
        flash('请选择要删除的预约', 'warning')
        return redirect(url_for('cms.vehicle_appointments_list'))
    
    try:
        # 查询所有要删除的预约
        appointments = VehicleAppointmentModel.query.filter(
            VehicleAppointmentModel.id.in_(appointment_ids)
        ).all()
        
        # 记录操作日志
        for appointment in appointments:
            log = UserLogModel(
                user_id=g.user.id,
                action='批量删除车辆预约',
                ip_address=request.remote_addr,
                details=json.dumps({
                    'appointment_id': appointment.id,
                    'license_plate': appointment.license_plate,
                    'name': appointment.name,
                    'status': appointment.status
                })
            )
            db.session.add(log)
            
            # 删除预约
            db.session.delete(appointment)
        
        db.session.commit()
        flash(f'已成功删除 {len(appointments)} 条预约记录', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'批量删除失败: {str(e)}', 'danger')
    
    return redirect(url_for('cms.vehicle_appointments_list'))

# =============================================== 轮播图管理 =========================================== #
@bp.route("/banners")
@permission_required(PermissionEnum.BANNER)
def banners_list():
    """轮播图列表页面"""
    banners = BannerModel.query.order_by(BannerModel.sort_order).all()
    return render_template("cms/banners_list.html", banners=banners)

@bp.route("/banners/add", methods=['GET', 'POST'])
@permission_required(PermissionEnum.BANNER)
def banner_add():
    """添加轮播图"""
    if request.method == "GET":
        form = BannerForm()
        return render_template("cms/banner_edit.html", form=form, is_add=True)
    else:
        form = BannerForm(request.form)
        
        try:
            # 获取表单数据
            title = request.form.get('title', '')
            image_url = request.form.get('image_url', '')
            link_url = request.form.get('link_url', '')
            sort_order = request.form.get('sort_order', 0, type=int)
            status = request.form.get('status', 1, type=int)
            
            # 处理图片上传
            image_file = request.files.get('image_file')
            if image_file and image_file.filename:
                # 验证文件类型
                allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
                file_ext = image_file.filename.rsplit('.', 1)[1].lower() if '.' in image_file.filename else ''
                
                if not file_ext or file_ext not in allowed_extensions:
                    flash(f"不支持的文件类型，请上传 {', '.join(allowed_extensions)} 格式的图片", "error")
                    return render_template("cms/banner_edit.html", form=form, is_add=True)
                
                # 验证文件大小（限制为2MB）
                max_size = 2 * 1024 * 1024  # 2MB
                image_file.seek(0, 2)  # 移动到文件末尾
                file_size = image_file.tell()  # 获取文件大小
                image_file.seek(0)  # 重置文件指针
                
                if file_size > max_size:
                    flash(f"文件大小超过限制（最大2MB），当前大小: {file_size / 1024 / 1024:.2f}MB", "error")
                    return render_template("cms/banner_edit.html", form=form, is_add=True)
                
                # 确保Flask上传目录存在
                upload_dir = os.path.join(current_app.static_folder, 'banners')
                if not os.path.exists(upload_dir):
                    os.makedirs(upload_dir)
                
                # 生成更安全唯一的文件名（使用uuid和时间戳）
                import uuid
                file_uuid = str(uuid.uuid4())
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                filename = secure_filename(image_file.filename)
                file_base, file_ext = os.path.splitext(filename)
                new_filename = f"{timestamp}_{file_uuid[:8]}_{file_base}{file_ext}"
                
                # 保存文件到Flask静态目录
                flask_file_path = os.path.join(upload_dir, new_filename)
                image_file.save(flask_file_path)
                
                # 尝试图片优化（可选）
                try:
                    from PIL import Image
                    img = Image.open(flask_file_path)
                    
                    # 保持宽高比的情况下限制最大尺寸（如果图片过大）
                    max_width = 1920
                    max_height = 1080
                    
                    if img.width > max_width or img.height > max_height:
                        img.thumbnail((max_width, max_height), Image.LANCZOS)
                        img.save(flask_file_path, optimize=True, quality=85)
                        print(f"图片已优化: {new_filename}")
                except ImportError:
                    print("缺少Pillow库，跳过图片优化")
                except Exception as e:
                    print(f"图片优化失败: {str(e)}")
                
                # 设置为相对URL路径
                image_url = f"/static/banners/{new_filename}"
            
            # 如果既没有上传文件也没有提供URL，则提示错误
            if not image_url:
                flash("请提供图片URL或上传图片，两者至少选择一项", "error")
                return render_template("cms/banner_edit.html", form=form, is_add=True)
            
            # 创建轮播图记录
            banner = BannerModel(
                title=title,
                image_url=image_url,
                link_url=link_url,
                sort_order=sort_order,
                status=status
            )
            db.session.add(banner)
            db.session.commit()
            
            flash("轮播图添加成功", "success")
            return redirect(url_for("cms.banners_list"))
            
        except Exception as e:
            db.session.rollback()
            import traceback
            error_details = traceback.format_exc()
            print(f"轮播图添加失败: {error_details}")
            flash(f"保存失败：{str(e)}", "error")
            return render_template("cms/banner_edit.html", form=form, is_add=True)

@bp.route("/banners/edit/<int:banner_id>", methods=['GET', 'POST'])
@permission_required(PermissionEnum.BANNER)
def banner_edit(banner_id):
    """编辑轮播图"""
    banner = BannerModel.query.get_or_404(banner_id)
    
    if request.method == "GET":
        form = BannerForm(obj=banner)
        return render_template("cms/banner_edit.html", form=form, banner=banner, is_add=False)
    else:
        try:
            # 获取表单数据
            banner.title = request.form.get('title', banner.title)
            banner.link_url = request.form.get('link_url', banner.link_url)
            banner.sort_order = request.form.get('sort_order', banner.sort_order, type=int)
            banner.status = request.form.get('status', banner.status, type=int)
            
            # 处理图片上传
            image_file = request.files.get('image_file')
            if image_file and image_file.filename:
                # 验证文件类型
                allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
                file_ext = image_file.filename.rsplit('.', 1)[1].lower() if '.' in image_file.filename else ''
                
                if not file_ext or file_ext not in allowed_extensions:
                    flash(f"不支持的文件类型，请上传 {', '.join(allowed_extensions)} 格式的图片", "error")
                    return render_template("cms/banner_edit.html", form=form, banner=banner, is_add=False)
                
                # 验证文件大小（限制为2MB）
                max_size = 2 * 1024 * 1024  # 2MB
                image_file.seek(0, 2)  # 移动到文件末尾
                file_size = image_file.tell()  # 获取文件大小
                image_file.seek(0)  # 重置文件指针
                
                if file_size > max_size:
                    flash(f"文件大小超过限制（最大2MB），当前大小: {file_size / 1024 / 1024:.2f}MB", "error")
                    return render_template("cms/banner_edit.html", form=form, banner=banner, is_add=False)
                
                # 确保Flask上传目录存在
                upload_dir = os.path.join(current_app.static_folder, 'banners')
                if not os.path.exists(upload_dir):
                    os.makedirs(upload_dir)
                
                # 生成更安全唯一的文件名（使用uuid和时间戳）
                import uuid
                file_uuid = str(uuid.uuid4())
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                filename = secure_filename(image_file.filename)
                file_base, file_ext = os.path.splitext(filename)
                new_filename = f"{timestamp}_{file_uuid[:8]}_{file_base}{file_ext}"
                
                # 保存文件到Flask静态目录
                flask_file_path = os.path.join(upload_dir, new_filename)
                image_file.save(flask_file_path)
                
                # 尝试图片优化（可选）
                try:
                    from PIL import Image
                    img = Image.open(flask_file_path)
                    
                    # 保持宽高比的情况下限制最大尺寸（如果图片过大）
                    max_width = 1920
                    max_height = 1080
                    
                    if img.width > max_width or img.height > max_height:
                        img.thumbnail((max_width, max_height), Image.LANCZOS)
                        img.save(flask_file_path, optimize=True, quality=85)
                        print(f"图片已优化: {new_filename}")
                except ImportError:
                    print("缺少Pillow库，跳过图片优化")
                except Exception as e:
                    print(f"图片优化失败: {str(e)}")
                
                # 获取旧图片文件路径以便删除
                if banner.image_url and banner.image_url.startswith('/static/banners/'):
                    old_filename = banner.image_url.replace('/static/banners/', '')
                    old_file_path = os.path.join(upload_dir, old_filename)
                    
                    # 尝试删除旧文件
                    try:
                        if os.path.exists(old_file_path):
                            os.remove(old_file_path)
                            print(f"已删除旧图片: {old_filename}")
                    except Exception as e:
                        print(f"删除旧图片失败: {str(e)}")
                
                # 设置为相对URL路径
                banner.image_url = f"/static/banners/{new_filename}"
            else:
                # 如果没有上传新文件，则使用表单中的URL
                new_image_url = request.form.get('image_url')
                if new_image_url:  # 只有当提供了新URL时才更新
                    # 如果以前的图片是上传的，尝试删除旧文件
                    if banner.image_url and banner.image_url.startswith('/static/banners/') and new_image_url != banner.image_url:
                        old_filename = banner.image_url.replace('/static/banners/', '')
                        old_file_path = os.path.join(current_app.static_folder, 'banners', old_filename)
                        
                        # 尝试删除旧文件
                        try:
                            if os.path.exists(old_file_path):
                                os.remove(old_file_path)
                                print(f"已删除旧图片: {old_filename}")
                        except Exception as e:
                            print(f"删除旧图片失败: {str(e)}")
                    
                    banner.image_url = new_image_url
            
            banner.update_time = datetime.now()
            db.session.commit()
            
            flash("轮播图更新成功", "success")
            return redirect(url_for("cms.banners_list"))
            
        except Exception as e:
            db.session.rollback()
            import traceback
            error_details = traceback.format_exc()
            print(f"轮播图编辑失败: {error_details}")
            flash(f"保存失败：{str(e)}", "error")
            return render_template("cms/banner_edit.html", form=form, banner=banner, is_add=False)

@bp.route("/banners/delete/<int:banner_id>", methods=['POST'])
@permission_required(PermissionEnum.BANNER)
def banner_delete(banner_id):
    """删除轮播图"""
    banner = BannerModel.query.get_or_404(banner_id)
    db.session.delete(banner)
    db.session.commit()
    flash("轮播图删除成功", "success")
    return redirect(url_for("cms.banners_list"))

# =============================================== 公告管理 =========================================== #
@bp.route("/notices")
@permission_required(PermissionEnum.NOTICE)
def notices_list():
    """公告列表页面"""
    notices = NoticeModel.query.order_by(NoticeModel.publish_time.desc()).all()
    return render_template("cms/notices_list.html", notices=notices)

@bp.route("/notices/add", methods=['GET', 'POST'])
@permission_required(PermissionEnum.NOTICE)
def notice_add():
    """添加公告"""
    if request.method == 'GET':
        form = NoticeForm()
        # 默认设置发布时间为当前时间
        form.publish_time.data = datetime.now()
        return render_template("cms/notice_edit.html", form=form, is_add=True)
    else:
        # 打印接收到的表单数据以便调试
        print(f"表单数据: {request.form}")
        
        # 先尝试直接处理HTML5格式的日期时间数据
        try:
            # 获取基本表单数据
            title = request.form.get('title')
            content = request.form.get('content')
            is_important = request.form.get('is_important', 0, type=int)
            status = request.form.get('status', 1, type=int)
            
            # 处理日期时间字段
            publish_time_str = request.form.get('publish_time')
            publish_time = datetime.strptime(publish_time_str, '%Y-%m-%dT%H:%M') if publish_time_str else datetime.now()
            
            end_time_str = request.form.get('end_time')
            end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M') if end_time_str and end_time_str.strip() else None
            
            # 创建公告对象
            notice = NoticeModel(
                title=title,
                content=content,
                publish_time=publish_time,
                end_time=end_time,
                is_important=is_important,
                status=status
            )
            db.session.add(notice)
            db.session.commit()
            flash("公告添加成功", "success")
            return redirect(url_for("cms.notices_list"))
        except Exception as e:
            db.session.rollback()
            flash(f"保存失败：{str(e)}", "error")
            
            # 回退到表单验证方式
            form = NoticeForm(request.form)
            if form.validate():
                try:
                    title = form.title.data
                    content = form.content.data
                    publish_time = form.publish_time.data
                    end_time = form.end_time.data
                    is_important = form.is_important.data
                    status = form.status.data
                    
                    notice = NoticeModel(
                        title=title,
                        content=content,
                        publish_time=publish_time,
                        end_time=end_time,
                        is_important=is_important,
                        status=status
                    )
                    db.session.add(notice)
                    db.session.commit()
                    flash("公告添加成功", "success")
                    return redirect(url_for("cms.notices_list"))
                except Exception as e:
                    db.session.rollback()
                    flash(f"保存失败：{str(e)}", "error")
            else:
                # 修复错误处理：form.messages 不存在，应该使用 form.errors
                for field, errors in form.errors.items():
                    for error in errors:
                        flash(f"{field}: {error}", "error")
        
        return render_template("cms/notice_edit.html", form=form, is_add=True)

@bp.route("/notices/edit/<int:notice_id>", methods=['GET', 'POST'])
@permission_required(PermissionEnum.NOTICE)
def notice_edit(notice_id):
    """编辑公告"""
    notice = NoticeModel.query.get_or_404(notice_id)
    
    if request.method == 'GET':
        form = NoticeForm(obj=notice)
        return render_template("cms/notice_edit.html", form=form, notice=notice, is_add=False)
    else:
        # 直接从请求中获取字段值，避免表单验证失败
        notice.title = request.form.get('title', notice.title)
        notice.content = request.form.get('content', notice.content)
        
        # 处理时间字段
        publish_time_str = request.form.get('publish_time')
        if publish_time_str:
            try:
                # 尝试解析HTML5日期时间格式
                notice.publish_time = datetime.strptime(publish_time_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                # 如果解析失败，保持原值
                pass
                
        end_time_str = request.form.get('end_time')
        if end_time_str and end_time_str.strip():
            try:
                notice.end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass
        else:
            notice.end_time = None
            
        notice.is_important = request.form.get('is_important', notice.is_important, type=int)
        notice.status = request.form.get('status', notice.status, type=int)
        notice.update_time = datetime.now()
        
        try:
            db.session.commit()
            flash("公告更新成功", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"保存失败：{str(e)}", "error")
            
        return redirect(url_for("cms.notices_list"))

@bp.route("/notices/delete/<int:notice_id>", methods=['POST'])
@permission_required(PermissionEnum.NOTICE)
def notice_delete(notice_id):
    """删除公告"""
    notice = NoticeModel.query.get_or_404(notice_id)
    db.session.delete(notice)
    db.session.commit()
    flash("公告删除成功", "success")
    return redirect(url_for("cms.notices_list"))

@bp.route("/notices/view/<int:notice_id>")
@permission_required(PermissionEnum.NOTICE)
def notice_view(notice_id):
    """查看公告详情"""
    notice = NoticeModel.query.get_or_404(notice_id)
    
    # 记录内容访问（CMS后台的访问也记录）
    from ..front.views import log_content_access
    log_content_access(notice_id, 'notice')
    
    return render_template("cms/notice_view.html", notice=notice, view_only=True)

# =============================================== 用户权限管理 =========================================== #
@bp.route("/user/<string:user_id>/permissions")
@permission_required(PermissionEnum.CMS_USER)
def get_user_permissions(user_id):
    """获取用户权限API"""
    user = UserModel.query.get(user_id)
    if not user:
        return restful.params_error(message="用户不存在")
    
    permissions_list = []
    
    # 如果用户有角色且角色有权限，返回权限列表
    if user.role and user.role.permissions:
        for permission in user.role.permissions:
            permissions_list.append({
                "id": permission.id,
                "name": permission.name.name,
                "description": permission.name.value
            })
    
    # 返回用户权限信息
    return restful.ok(data={
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "role_id": user.role_id if user.role else None,
        "role_name": user.role.name if user.role else None,
        "permissions": permissions_list
    })

@bp.route("/role/<int:role_id>/permissions")
@permission_required(PermissionEnum.CMS_USER)
def get_role_permissions(role_id):
    """获取角色权限API"""
    role = RoleModel.query.get(role_id)
    if not role:
        return restful.params_error(message="角色不存在")
    
    permissions_list = []
    
    # 获取角色的权限列表
    for permission in role.permissions:
        permissions_list.append({
            "id": permission.id,
            "name": permission.name.name,
            "description": permission.name.value
        })
    
    return restful.ok(data={
        "role_id": role.id,
        "role_name": role.name,
        "role_desc": role.desc,
        "permissions": permissions_list
    })

@bp.route("/user/<string:user_id>/update-role", methods=['POST'])
@permission_required(PermissionEnum.CMS_USER)
def update_user_role(user_id):
    """更新用户角色API"""
    user = UserModel.query.get(user_id)
    if not user:
        return restful.params_error(message="用户不存在")
    
    role_id = request.form.get('role_id', type=int)
    if not role_id:
        return restful.params_error(message="请选择角色")
    
    role = RoleModel.query.get(role_id)
    if not role:
        return restful.params_error(message="角色不存在")
    
    # 检查是否尝试将用户设置为超级管理员
    if role.name == '超级管理员':
        return restful.params_error(message="不能将用户设置为超级管理员")
    
    # 更新用户角色
    user.role = role
    db.session.commit()
    
    # 记录操作日志
    if hasattr(g, 'user') and g.user:
        log = UserLogModel(
            user_id=g.user.id,
            action="修改用户权限",
            ip_address=request.remote_addr,
            device_info=request.user_agent.string,
            details=f"修改用户 {user.username}({user.id}) 的角色为 {role.name}"
        )
        db.session.add(log)
        db.session.commit()
    
    return restful.ok(message="用户角色更新成功")

# =============================================== 权限管理页面 =========================================== #
@bp.route("/permissions")
@permission_required(PermissionEnum.CMS_USER)
def permission_management():
    """权限管理页面"""
    # 获取分页参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # 获取筛选参数
    role_filter = request.args.get('role', '')
    user_type_filter = request.args.get('user_type', '')
    search_query = request.args.get('search', '')
    
    # 构建查询
    query = UserModel.query
    
    # 应用角色筛选
    if role_filter:
        query = query.filter(UserModel.role_id == role_filter)
    
    # 应用用户类型筛选
    if user_type_filter == 'staff':
        query = query.filter(UserModel.is_staff == True)
    elif user_type_filter == 'front':
        query = query.filter(UserModel.is_staff == False)
    
    # 应用搜索条件
    if search_query:
        search_pattern = f'%{search_query}%'
        query = query.filter(
            db.or_(
                UserModel.username.ilike(search_pattern),
                UserModel.email.ilike(search_pattern),
                UserModel.phone.ilike(search_pattern)  # 添加手机号搜索
            )
        )
    
    # 执行分页查询
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    users = pagination.items
    
    # 获取所有角色
    all_roles = RoleModel.query.all()
    
    return render_template(
        'cms/permission_management.html',
        users=users,
        pagination=pagination,
        all_roles=all_roles,
        role_filter=role_filter,
        user_type_filter=user_type_filter,
        search_query=search_query
    )
