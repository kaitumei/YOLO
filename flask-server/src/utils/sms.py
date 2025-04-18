#!/usr/bin/python
# -*- coding: utf-8 -*-
import requests
from flask import current_app
import logging
import json
import os

def send_sms(mobile, code):
    """
    发送短信验证码
    :param mobile: 手机号码
    :param code: 验证码
    :return: 是否成功
    """
    # 检查是否在开发环境中
    debug_mode = os.environ.get('FLASK_ENV') == 'development' or os.environ.get('FLASK_DEBUG') == '1'
    
    # 记录验证码到日志(仅用于调试)
    logging.info(f"为手机号 {mobile} 生成的验证码: {code}")
    
    # 在调试模式下，跳过实际的短信发送，直接返回成功
    if debug_mode:
        logging.info(f"调试模式：模拟发送验证码 {code} 到 {mobile} 成功")
        return True
    
    try:
        url = "https://gyytz.market.alicloudapi.com/sms/smsSend"
        appcode = '8ef69e9d088d48b58414ea27aa574d11'  # 实际使用时建议从配置中读取
        smsSignId = "2e65b1bb3d054466b82f0c9d125465e2"
        templateId = "908e94ccf08b4476ba6c876d13f084ad"
        
        # 使用简洁的JSON格式 - code和minute都是字符串类型，确保不会产生额外字符
        param_dict = {
            "code": code,  # 验证码，直接传入数字
            "minute": "5"  # 有效期，固定为5分钟
        }
        param = json.dumps(param_dict)
        
        data = {
            "mobile": mobile,
            "smsSignId": smsSignId,
            "templateId": templateId,
            "param": param
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded", 
            "Authorization": "APPCODE " + appcode
        }
        
        logging.info(f"准备发送短信: URL={url}, 手机号={mobile}, 参数={param}")
        
        # 记录请求参数
        logging.info(f"发送短信请求: headers={headers}, data={data}")
        
        # 在开发环境尝试最多3次
        max_retries = 3 if debug_mode else 1
        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, data=data, timeout=10)
                
                # 记录完整响应
                logging.info(f"短信API响应状态码: {response.status_code}")
                logging.info(f"短信API响应头: {response.headers}")
                logging.info(f"短信API响应内容: {response.text}")
                
                # 根据响应状态码判断是否成功
                if response.status_code == 200:
                    try:
                        resp_json = response.json()
                        logging.info(f"短信API响应JSON解析结果: {resp_json}")
                        
                        if resp_json.get('code') == '0':  # 根据API文档判断成功状态码
                            logging.info(f"向 {mobile} 发送短信成功")
                            return True
                        else:
                            error_msg = resp_json.get('message', '未知错误')
                            logging.error(f"短信API返回错误: code={resp_json.get('code')}, message={error_msg}")
                            if attempt < max_retries - 1:
                                logging.info(f"第 {attempt+1} 次尝试失败，将重试")
                                continue
                            
                            # 如果是调试模式且最后一次尝试也失败，则模拟发送成功
                            if debug_mode:
                                logging.warning(f"调试模式：API调用失败，模拟发送成功")
                                return True
                                
                            return False
                    except Exception as e:
                        logging.error(f"解析短信API响应时出错: {e}")
                        # 尝试直接检查文本响应
                        if '"code":"0"' in response.text:
                            logging.info(f"通过文本检查确认短信发送成功")
                            return True
                            
                        # 如果是调试模式且解析失败，则模拟发送成功
                        if debug_mode and attempt == max_retries - 1:
                            logging.warning(f"调试模式：响应解析失败，模拟发送成功")
                            return True
                            
                        logging.error(f"短信API响应解析失败: {e}")
                        if attempt < max_retries - 1:
                            continue
                        return False
                else:
                    logging.error(f"短信API请求失败，状态码: {response.status_code}, 响应: {response.text}")
                    if attempt < max_retries - 1:
                        continue
                        
                    # 如果是调试模式且最后一次尝试也失败，则模拟发送成功
                    if debug_mode:
                        logging.warning(f"调试模式：API请求失败，模拟发送成功")
                        return True
                        
                    return False
                    
            except (requests.Timeout, requests.ConnectionError) as e:
                logging.error(f"短信请求失败: {str(e)}")
                if attempt < max_retries - 1:
                    logging.info(f"第 {attempt+1} 次尝试失败，将重试")
                    continue
                
                # 如果是调试模式且最后一次尝试也失败，则模拟发送成功
                if debug_mode:
                    logging.warning(f"调试模式：API连接失败，模拟发送成功")
                    return True
                    
                return False
                
        # 所有尝试都失败
        return False
            
    except Exception as e:
        logging.error(f"发送短信时发生异常: {str(e)}", exc_info=True)
        
        # 如果是调试模式，则模拟发送成功
        if debug_mode:
            logging.warning(f"调试模式：发生异常，模拟发送成功")
            return True
            
        return False 