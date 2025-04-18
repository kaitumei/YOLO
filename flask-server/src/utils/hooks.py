# 这段代码用于在 Flask 应用程序中处理一些常见的错误情况，例如 404 Not Found、500 Internal Server Error 和 401 Unauthorized。下面是加上中文注释后的代码：
from flask import session, g, url_for, request, current_app
import time
from ..blueprints.front.models import UserModel
from flask import render_template
from src.utils.exts import avatars

# 定义一个 bbs_before_request 函数，在每次请求时被调用
def bbs_before_request():
    # 默认将g.user设置为None
    g.user = None
    
    # 如果 session 中存在 user_id，则从数据库中获取用户信息
    if 'user_id' in session:
        user_id = session['user_id']
        try:
            user = UserModel.query.get(user_id)
            if user:
                # 确保头像URL格式正确
                if user.avatar and not user.avatar.startswith('/'):
                    # 检查avatar是否已包含url_for生成的路径
                    if not user.avatar.startswith('/media/'):
                        parts = user.avatar.split('/')
                        if len(parts) > 0:
                            avatar_filename = '/'.join(parts)
                            user.avatar = url_for('front.media_file', filename=avatar_filename)
                
                # 检查是否需要添加时间戳，防止缓存
                if user.avatar and 't=' not in user.avatar:
                    # 分离基本URL和查询参数
                    avatar_base = user.avatar.split('?')[0]
                    timestamp = int(time.time())
                    
                    # 这里可能需要改成静态文件URL
                    if avatar_base.startswith('/'):
                        user.avatar = f"{avatar_base}?t={timestamp}"
                
                # 检查session中是否有头像更新标志
                if session.get('avatar_updated'):
                    # 清除标志
                    session.pop('avatar_updated', None)
                
                setattr(g, 'user', user)
        except Exception as e:
            current_app.logger.error(f"获取用户信息时出错: {str(e)}")
    
    # 将avatars对象添加到g中，供模板使用
    g.avatars = avatars

# 定义一个 bbs_404_error 函数，用于处理 404 Not Found 错误
def bbs_404_error(error):
    return render_template("errors/404.html"), 404

# 定义一个 bbs_500_error 函数，用于处理 500 Internal Server Error 错误
def bbs_500_error(error):
    return render_template("errors/500.html"), 500

# 定义一个 bbs_401_error 函数，用于处理 401 Unauthorized 错误
def bbs_401_error(error):
    return render_template("errors/401.html"), 401
