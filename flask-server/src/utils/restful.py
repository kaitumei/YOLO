from flask import jsonify
from enum import Enum

class HttpCode(Enum):
    # 响应正常
    OK = 200
    # 未授权
    UNAUTHORIZED = 401
    # 没有权限
    FORBIDDEN = 403
    # 参数错误
    BAD_REQUEST = 400
    # 服务器内部错误
    INTERNAL_SERVER_ERROR = 500
    # 创建成功
    CREATED = 201
    # 没有内容
    NO_CONTENT = 204
    # 未找到
    NOT_FOUND = 404

def _restful_result(code, message=None, data=None):
    # 生成 JSON 响应
    return jsonify({
        "code": code.value,
        "message": message or code.name,
        "data": data or None
    }), code.value

def ok(message=None, data=None):
    return _restful_result(HttpCode.OK, message, data)

def unlogin_error(message="未登录！"):
    return _restful_result(HttpCode.UNAUTHORIZED, message)

def permission_error(message="没有访问权限！"):
    return _restful_result(HttpCode.FORBIDDEN, message)

def params_error(message="参数错误！"):
    return _restful_result(HttpCode.BAD_REQUEST, message)

def server_error(message="服务器内部错误！"):
    return _restful_result(HttpCode.INTERNAL_SERVER_ERROR, message)

def created(message=None, data=None):
    return _restful_result(HttpCode.CREATED, message, data)

def no_content(message=None, data=None):
    return _restful_result(HttpCode.NO_CONTENT, message, data)

def not_found(message="未找到！"):
    return _restful_result(HttpCode.NOT_FOUND, message, data=None)