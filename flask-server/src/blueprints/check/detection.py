"""
事故检测相关工具函数
"""
import os
import json
import base64
from datetime import datetime
from collections import deque

# 事故类别名称列表
ACCIDENT_CLASS_NAMES = ['accident', 'car accident', 'traffic accident', '事故车', '事故', 'accident car']

def is_accident_detection(detection):
    """
    检查检测结果是否为事故
    """
    if not detection:
        return False
        
    # 提取类别名称
    class_name = detection.get('class', '') or detection.get('class_name', '') or detection.get('name', '') or ''
    class_name = class_name.lower()
    
    # 检查是否匹配事故类别
    for accident_class in ACCIDENT_CLASS_NAMES:
        if accident_class.lower() in class_name:
            return True
    
    return False

def check_frame_for_accident(detections):
    """
    检查整个帧的检测结果是否包含事故
    """
    if not detections:
        return False
        
    # 处理单个检测对象
    if isinstance(detections, dict):
        if is_accident_detection(detections):
            return True
        # 检查嵌套的检测结果
        nested_detections = detections.get('detections', [])
        if nested_detections:
            return check_frame_for_accident(nested_detections)
    
    # 处理检测列表
    if isinstance(detections, list):
        for det in detections:
            if check_frame_for_accident(det):
                return True
    
    return False

def save_accident_image(image_data, filename=None):
    """
    保存事故图像到文件系统
    """
    from config.prod import BaseConfig
    
    try:
        # 解码Base64图像
        if isinstance(image_data, str):
            # 如果是Base64字符串
            image_bytes = base64.b64decode(image_data)
        else:
            # 如果已经是字节数据
            image_bytes = image_data
            
        # 创建事故捕捉目录
        accident_dir = os.path.join(BaseConfig.MEDIA_ROOT, 'accidents')
        os.makedirs(accident_dir, exist_ok=True)
        
        # 生成文件名
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"accident_{timestamp}.jpg"
            
        # 保存图像文件
        save_path = os.path.join(accident_dir, filename)
        with open(save_path, 'wb') as f:
            f.write(image_bytes)
            
        return {
            'success': True,
            'path': save_path,
            'url': f"/media/accidents/{filename}"
        }
    except Exception as e:
        print(f"[事故捕捉] 保存图像失败: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
