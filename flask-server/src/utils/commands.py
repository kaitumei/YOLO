import click
from src.utils.exts import db
from ..blueprints.common.models import PermissionEnum
from ..blueprints.cms.models import PermissionModel
from ..blueprints.cms.models import RoleModel
from ..blueprints.front.models import UserModel
from sqlalchemy.sql import text
from sqlalchemy import insert, select


def create_permission():
    for permission_name in dir(PermissionEnum):
        if permission_name.startswith('__'):
            continue
        permission_enum = getattr(PermissionEnum, permission_name)
        # 检查权限是否已存在
        exists = PermissionModel.query.filter_by(name=permission_enum).first()
        if not exists:
            permission = PermissionModel(name=permission_enum)
            db.session.add(permission)
            click.echo(f'添加权限: {permission_enum.value}')
    db.session.commit()
    click.echo('权限创建完成')

# 生成初始角色
def create_role():
    # 普通用户
    normal_user = RoleModel(name='普通用户', desc='普通用户角色')
    
    # 运营
    operate = RoleModel(name='运营', desc='拥有板块和内容权限')
    operate.permissions = PermissionModel.query.filter(PermissionModel.name.in_([
        PermissionEnum.BOARD,
        PermissionEnum.VIEW_STATS,
        PermissionEnum.VEHICLE_APPOINTMENT
    ])).all()

    # 管理员
    admin = RoleModel(name='管理员', desc='拥有板块、内容、日志、前台用户权限')
    admin.permissions = PermissionModel.query.filter(PermissionModel.name.in_([
        PermissionEnum.BOARD,
        PermissionEnum.LOGS,
        PermissionEnum.VIEW_STATS,
        PermissionEnum.FRONT_USER,
        PermissionEnum.VEHICLE_APPOINTMENT
    ])).all()

    # 超级管理员
    super_admin = RoleModel(name='超级管理员', desc='拥有所有权限')
    super_admin.permissions = PermissionModel.query.all()

    db.session.add_all([normal_user, operate, admin, super_admin])
    db.session.commit()
    click.echo('角色创建完成')

def create_test_user():
    super_admin_role = RoleModel.query.filter_by(name='超级管理员').first()
    zhangsan = UserModel(username='张三', email='zhangsan@hytt.com', password='123456', is_staff=True,role=super_admin_role)

    admin_role = RoleModel.query.filter_by(name='管理员').first()
    lisi = UserModel(username='李四', email='lisi@hytt.com', password='123456', is_staff=True,role=admin_role)

    operate_role = RoleModel.query.filter_by(name='运营').first()
    wangwu = UserModel(username='王五', email='wangwu@hytt.com', password='123456', is_staff=True,role=operate_role)

    db.session.add_all([zhangsan, lisi, wangwu])
    db.session.commit()
    click.echo('测试用户创建完成')

# 创建管理员
@click.option("--username", '-u', prompt="请输入管理员用户名", help="管理员用户名")
@click.option("--email", '-e', prompt="请输入管理员邮箱", help="管理员邮箱")
@click.option("--password", '-p', prompt="请输入管理员密码", hide_input=True, help="管理员密码")
def create_admin(username, email, password):

    admin_role = RoleModel.query.filter_by(name='管理员').first()
    admin_user = UserModel(
        username=username,
        email=email,
        password=password,
        is_staff=True,
        role=admin_role
    )
    db.session.add(admin_user)
    db.session.commit()
    click.echo('管理员创建完成')

# 更新角色权限
def update_permissions():
    """更新角色权限"""
    try:
        # 确保有BANNER和NOTICE权限
        with db.engine.connect() as conn:
            # 检查BANNER权限是否存在
            banner_exists = conn.execute(text(
                "SELECT id FROM permission WHERE name = 'BANNER'"
            )).fetchone()
            
            if not banner_exists:
                conn.execute(text(
                    "INSERT INTO permission (name) VALUES ('BANNER')"
                ))
                conn.commit()
                print(f"添加BANNER权限")
            
            # 获取BANNER权限ID
            banner_id = conn.execute(text(
                "SELECT id FROM permission WHERE name = 'BANNER'"
            )).fetchone()[0]
            
            # 检查NOTICE权限是否存在
            notice_exists = conn.execute(text(
                "SELECT id FROM permission WHERE name = 'NOTICE'"
            )).fetchone()
            
            if not notice_exists:
                conn.execute(text(
                    "INSERT INTO permission (name) VALUES ('NOTICE')"
                ))
                conn.commit()
                print(f"添加NOTICE权限")
            
            # 获取NOTICE权限ID
            notice_id = conn.execute(text(
                "SELECT id FROM permission WHERE name = 'NOTICE'"
            )).fetchone()[0]
            
            # 获取管理员角色ID
            admin_id = conn.execute(text(
                "SELECT id FROM role WHERE name = '管理员'"
            )).fetchone()[0]
            
            # 获取超级管理员角色ID
            super_admin_id = conn.execute(text(
                "SELECT id FROM role WHERE name = '超级管理员'"
            )).fetchone()[0]
            
            # 为管理员角色添加BANNER权限
            admin_has_banner = conn.execute(text(
                "SELECT * FROM role_permission_table WHERE role_id = :role_id AND permission_id = :permission_id"
            ), {"role_id": admin_id, "permission_id": banner_id}).fetchone()
            
            if not admin_has_banner:
                conn.execute(text(
                    "INSERT INTO role_permission_table (role_id, permission_id) VALUES (:role_id, :permission_id)"
                ), {"role_id": admin_id, "permission_id": banner_id})
                print(f"为管理员角色添加BANNER权限")
            
            # 为管理员角色添加NOTICE权限
            admin_has_notice = conn.execute(text(
                "SELECT * FROM role_permission_table WHERE role_id = :role_id AND permission_id = :permission_id"
            ), {"role_id": admin_id, "permission_id": notice_id}).fetchone()
            
            if not admin_has_notice:
                conn.execute(text(
                    "INSERT INTO role_permission_table (role_id, permission_id) VALUES (:role_id, :permission_id)"
                ), {"role_id": admin_id, "permission_id": notice_id})
                print(f"为管理员角色添加NOTICE权限")
            
            # 为超级管理员角色添加BANNER权限
            super_admin_has_banner = conn.execute(text(
                "SELECT * FROM role_permission_table WHERE role_id = :role_id AND permission_id = :permission_id"
            ), {"role_id": super_admin_id, "permission_id": banner_id}).fetchone()
            
            if not super_admin_has_banner:
                conn.execute(text(
                    "INSERT INTO role_permission_table (role_id, permission_id) VALUES (:role_id, :permission_id)"
                ), {"role_id": super_admin_id, "permission_id": banner_id})
                print(f"为超级管理员角色添加BANNER权限")
            
            # 为超级管理员角色添加NOTICE权限
            super_admin_has_notice = conn.execute(text(
                "SELECT * FROM role_permission_table WHERE role_id = :role_id AND permission_id = :permission_id"
            ), {"role_id": super_admin_id, "permission_id": notice_id}).fetchone()
            
            if not super_admin_has_notice:
                conn.execute(text(
                    "INSERT INTO role_permission_table (role_id, permission_id) VALUES (:role_id, :permission_id)"
                ), {"role_id": super_admin_id, "permission_id": notice_id})
                print(f"为超级管理员角色添加NOTICE权限")
            
            conn.commit()
        
        print("角色权限更新完成")
    except Exception as e:
        db.session.rollback()
        print(f"更新权限时发生错误: {e}")

@click.command()
def update_permissions_command():
    """更新角色权限命令"""
    update_permissions()
    click.echo('角色权限更新完成')

# 注册命令
def register_commands(app):
    app.cli.add_command(create_admin)
    app.cli.add_command(update_permissions_command)
