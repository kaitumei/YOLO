"""
YOLO Vehicle Detection Module

This module provides vehicle detection, license plate recognition, accident detection, etc.
"""

# Version information
__version__ = '1.0.1'

# Import sub-modules
from .detector import Detector, get_detector
from .video_processor import process_video, detect_video_objects
from .image_processor import process_image, process_images_batch
from .license_plate_ocr import get_license_plate_ocr, LicensePlateOCR
from .vehicle_analyzer import identify_vehicle_color
from .class_mapper import get_vehicle_class_name, load_classes

import os
import torch

# 默认模型路径
DEFAULT_MODEL_PATH = os.environ.get('YOLO_MODEL_PATH', 'models/zhlkv3.onnx')
DEFAULT_DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

# 全局配置
CONFIG = {
    'model_path': DEFAULT_MODEL_PATH,
    'device': DEFAULT_DEVICE,
    'conf_threshold': 0.4,
    'use_chinese': True,
    'draw_boxes': True,  # 确保绘制边界框开启
    'use_class_color': True  # 使用类别颜色（True）或车辆实际颜色（False）
}

# 全局检测器实例
_detector = None

def get_detector(model_path=None, device=None, conf_threshold=None, classes_file=None):
    """
    获取或创建检测器实例
    """
    global _detector
    
    # 如果提供了参数，创建新的检测器
    if model_path or device or conf_threshold or classes_file:
        return Detector(
            model_path=model_path or CONFIG['model_path'],
            device=device or CONFIG['device'],
            conf_threshold=conf_threshold or CONFIG['conf_threshold'],
            classes_file=classes_file
        )
    
    # 否则使用全局单例
    if _detector is None:
        _detector = Detector(
            model_path=CONFIG['model_path'],
            device=CONFIG['device'],
            conf_threshold=CONFIG['conf_threshold']
        )
    
    return _detector

# Export variables
__all__ = [
    'Detector', 
    'get_detector', 
    'process_video',
    'process_image',
    'process_images_batch',
    'get_license_plate_ocr',
    'LicensePlateOCR',
    'identify_vehicle_color',
    'get_vehicle_class_name',
    'load_classes',
    'detect_video_objects',
    'CONFIG'
]
