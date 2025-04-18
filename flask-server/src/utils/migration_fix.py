from flask import current_app
from src.utils.exts import db
from sqlalchemy import text
from src.blueprints.common.models import PermissionEnum
from src.blueprints.cms.models import PermissionModel, RoleModel

def fix_media_permission():
    """
    将数据库中的MEDIA权限枚举值替换为BANNER
    """
    print("开始修复权限枚举值...")
    
    # 输出当前有效的权限枚举值
    print("当前有效的权限枚举值:", [e.name for e in PermissionEnum])
    
    # 首先验证是否存在MEDIA记录
    with db.engine.connect() as conn:
        # 使用原生SQL查询确认是否存在MEDIA权限记录
        result = conn.execute(text("SELECT * FROM permission WHERE name = 'MEDIA'"))
        records = result.fetchall()
        
        if not records:
            print("数据库中不存在MEDIA权限记录，无需修复。")
            return
        
        print(f"发现{len(records)}条MEDIA权限记录，开始修复...")
        
        # 首先找到BANNER权限的ID
        banner_permission = PermissionModel.query.filter_by(name=PermissionEnum.BANNER).first()
        
        if not banner_permission:
            print("错误：数据库中不存在BANNER权限记录，无法修复。")
            return
        
        banner_id = banner_permission.id
        print(f"BANNER权限ID: {banner_id}")
        
        # 找到使用MEDIA权限的角色
        media_roles_result = conn.execute(text(
            "SELECT role_id FROM role_permission_table WHERE permission_id IN "
            "(SELECT id FROM permission WHERE name = 'MEDIA')"
        ))
        media_roles = [row[0] for row in media_roles_result]
        
        if media_roles:
            print(f"发现{len(media_roles)}个角色使用MEDIA权限: {media_roles}")
            
            # 为这些角色添加BANNER权限（如果没有）
            for role_id in media_roles:
                # 检查角色是否已有BANNER权限
                check_result = conn.execute(text(
                    "SELECT 1 FROM role_permission_table "
                    "WHERE role_id = :role_id AND permission_id = :banner_id"
                ), {"role_id": role_id, "banner_id": banner_id})
                
                if not check_result.fetchone():
                    # 添加BANNER权限
                    conn.execute(text(
                        "INSERT INTO role_permission_table (role_id, permission_id) "
                        "VALUES (:role_id, :banner_id)"
                    ), {"role_id": role_id, "banner_id": banner_id})
                    conn.commit()
                    print(f"为角色 {role_id} 添加BANNER权限")
        
        # 删除MEDIA权限记录
        conn.execute(text(
            "DELETE FROM role_permission_table WHERE permission_id IN "
            "(SELECT id FROM permission WHERE name = 'MEDIA')"
        ))
        conn.commit()
        
        conn.execute(text("DELETE FROM permission WHERE name = 'MEDIA'"))
        conn.commit()
        
        print("成功删除MEDIA权限记录并将关联角色更新为使用BANNER权限")
    
    print("权限修复完成！")

if __name__ == "__main__":
    # 当直接运行此脚本时
    from flask import Flask
    from src.utils.exts import db
    from src.config import DevelopmentConfig
    
    app = Flask(__name__)
    app.config.from_object(DevelopmentConfig)
    db.init_app(app)
    
    with app.app_context():
        fix_media_permission() 