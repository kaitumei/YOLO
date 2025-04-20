# 权限限制

from functools import wraps
from flask import g
from flask import redirect
from flask import url_for
from flask import flash
from flask import abort

def login_required(func):
        @wraps(func)
        def inner(*args, **kwargs):
            if not hasattr(g, 'user') or g.user is None:
                return redirect(url_for('front.login'))
            elif not g.user.is_active:
                flash("您的账号已被禁用！")
                return redirect(url_for('front.login'))
            else:
                return func(*args, **kwargs)
        return inner

def permission_required(permission):
    def outer(func):
        @wraps(func)
        def inner(*args, **kwargs):
            if hasattr(g, 'user') and g.user and g.user.has_permission(permission):
                return func(*args, **kwargs)
            else:
                flash("您没有权限访问该页面！")
                return abort(403)
        return inner
    return outer



