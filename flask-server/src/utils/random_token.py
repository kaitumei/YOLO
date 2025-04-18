import os
import secrets
import string
import base64

def generate_token(length=32):
    """
    生成指定长度的随机令牌
    
    参数:
        length (int): 令牌的长度，默认为32
        
    返回:
        str: 生成的随机令牌
    """
    # 使用secrets模块生成安全的随机字节
    random_bytes = secrets.token_bytes(length)
    
    # 将随机字节转换为URL安全的base64编码，并去掉填充字符
    token = base64.urlsafe_b64encode(random_bytes).decode('utf-8').replace('=', '')
    
    # 截取指定长度
    return token[:length]

def generate_simple_token(length=32):
    """
    生成简单的随机令牌，由字母和数字组成
    
    参数:
        length (int): 令牌的长度，默认为32
        
    返回:
        str: 生成的随机令牌
    """
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length)) 