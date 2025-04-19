import cv2
import numpy as np
from ultralytics import YOLO
import os
import time
from datetime import datetime
import torch
import hashlib
import pickle
from PIL import Image, ImageDraw, ImageFont
import concurrent.futures
from tqdm import tqdm

# 导入子模块
from .utils import draw_text_pil, draw_fancy_box, calculate_iou, preprocess_license_plate, format_license_plate
from .license_plate_ocr import LicensePlateOCR, identify_plate_color
from .vehicle_analyzer import identify_vehicle_color
from .class_mapper import get_vehicle_class_name, load_classes, DEFAULT_CLASSES, DEFAULT_CLASS_NAMES_ZH

class Detector:
    """
    YOLO检测器类
    提供车辆检测、车牌识别、事故检测和违章检测功能
    """
    def __init__(self, model_path=None, model=None, device='cpu', conf_threshold=0.4, 
                 classes_file=None, use_chinese=True, batch_size=1):
        """
        初始化检测器
        
        参数:
            model_path: YOLO模型路径
            model: 已加载的YOLO模型实例（与model_path二选一）
            device: 运行设备，'cuda'或'cpu'
            conf_threshold: 最小置信度
            classes_file: 类别文件路径
            use_chinese: 是否使用中文类名
            batch_size: 批处理大小
        """
        self.device = device
        self.conf_threshold = conf_threshold
        self.use_chinese = use_chinese
        self.batch_size = batch_size
        self.is_onnx = False  # 默认非ONNX模型
        
        # 加载模型
        if model is not None:
            self.model = model
        elif model_path is not None:
            self.model = self._load_model(model_path, device)
        else:
            raise ValueError("必须提供model_path或model参数")
            
        # 加载类别
        if classes_file and os.path.exists(classes_file):
            self.classes = load_classes(classes_file)
            print(f"已加载类别文件: {classes_file}")
        else:
            self.classes = DEFAULT_CLASSES.copy()
            print("使用默认类别")
            
        self.class_names_zh = DEFAULT_CLASS_NAMES_ZH.copy()
        
        # 初始化车牌OCR
        self.plate_ocr = LicensePlateOCR(use_gpu=(device=='cuda'))
        
        # 设置识别缓存
        self.recognition_cache = {}
        
    def _load_model(self, model_path, device):
        """加载YOLO模型"""
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"找不到模型文件: {model_path}")
            
        try:
            # 检查是否为ONNX模型
            if model_path.lower().endswith('.onnx'):
                # ONNX模型使用特定的加载方式
                print(f"检测到ONNX模型: {model_path}")
                model = YOLO(model_path)
                print(f"ONNX模型加载成功: {model_path} (设备: {device})")
                # 注意：不要直接使用to(device)方法，在predict时指定设备
                self.is_onnx = True
            else:
                # PT模型使用标准PyTorch方式加载
                model = YOLO(model_path).to(device)
                self.is_onnx = False
                print(f"PyTorch模型加载成功: {model_path} (设备: {device})")
            
            return model
        except Exception as e:
            raise Exception(f"模型加载失败: {e}")
            
    def detect_objects(self, image, conf_threshold=None, detect_vehicles=True, 
                       detect_plates=True, detect_accidents=False, detect_violations=False):
        """
        检测图像中的对象
        
        参数:
            image: 输入图像（OpenCV格式）
            conf_threshold: 置信度阈值，为None则使用默认值
            detect_vehicles: 是否检测车辆
            detect_plates: 是否检测车牌
            detect_accidents: 是否检测事故
            detect_violations: 是否检测违章
            
        返回:
            result_image: 标注后的图像
            detections: 检测结果列表
        """
        if conf_threshold is None:
            conf_threshold = self.conf_threshold
            
        result_image = image.copy()
        all_detections = []
        
        # 确定要检测的类别
        classes_to_detect = []
        if detect_vehicles:
            classes_to_detect.extend([0, 1, 2, 3, 4, 5, 6, 7])  # 车辆类别
        if detect_plates:
            classes_to_detect.append(8)  # 车牌类别
        if detect_accidents:
            classes_to_detect.append(9)  # 事故类别
        if detect_violations:
            classes_to_detect.extend([10, 11])  # 违章类别
            
        # 如果未指定类别，检测所有类别
        if not classes_to_detect:
            classes_to_detect = None
            
        # 运行推理
        try:
            # 对ONNX模型需要特殊处理，在predict时指定设备
            if hasattr(self, 'is_onnx') and self.is_onnx:
                results = self.model.predict(
                    source=image, 
                    conf=conf_threshold, 
                    classes=classes_to_detect, 
                    device=self.device,
                    verbose=False
                )
            else:
                # 使用常规方式处理PT模型
                results = self.model(image, conf=conf_threshold, classes=classes_to_detect, verbose=False)
            
            # 处理检测结果
            for r in results:
                boxes = r.boxes
                
                for box in boxes:
                    # 获取边界框
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    
                    # 获取置信度
                    conf = float(box.conf[0])
                    
                    # 获取类别
                    cls_id = int(box.cls[0])
                    class_name = get_vehicle_class_name(cls_id, self.use_chinese, 
                                                      self.classes, self.class_names_zh)
                    
                    # 确定对象类型
                    box_type = self._determine_box_type(cls_id)
                    
                    # 创建检测结果字典
                    detection = {
                        "coordinates": [x1, y1, x2, y2],
                        "confidence": conf,
                        "class_id": cls_id,
                        "class_name": class_name,
                        "type": box_type
                    }
                    
                    # 如果是车牌且启用了车牌检测，尝试识别车牌号码
                    if cls_id == 8 and detect_plates and self.plate_ocr.is_available():
                        plate_text, plate_conf = self._recognize_license_plate(image, [x1, y1, x2, y2])
                        if plate_text:
                            detection["plate_text"] = plate_text
                            detection["plate_conf"] = plate_conf
                            
                            # 识别车牌颜色
                            plate_region = image[y1:y2, x1:x2]
                            plate_color, _ = identify_plate_color(plate_region)
                            detection["plate_color"] = plate_color
                    
                    # 如果是车辆，尝试识别车辆颜色
                    if cls_id < 8 and detect_vehicles:
                        vehicle_region = image[y1:y2, x1:x2]
                        color_name, rgb_color = identify_vehicle_color(vehicle_region)
                        detection["vehicle_color"] = color_name
                        detection["vehicle_rgb"] = rgb_color
                    
                    # 绘制边界框
                    # 基于类型设置颜色
                    custom_color = None
                    
                    # 根据类别ID设置不同颜色
                    if cls_id == 0:  # 小汽车
                        custom_color = (0, 255, 0)  # 绿色 (BGR)
                    elif cls_id == 1:  # 公交车
                        custom_color = (255, 128, 0)  # 蓝紫色
                    elif cls_id == 2:  # 油罐车
                        custom_color = (0, 0, 255)  # 红色
                    elif cls_id == 3:  # 集装箱卡车
                        custom_color = (255, 0, 0)  # 蓝色
                    elif cls_id == 4:  # 卡车
                        custom_color = (0, 255, 255)  # 黄色
                    elif cls_id == 5:  # 面包车
                        custom_color = (128, 0, 128)  # 紫色
                    elif cls_id == 6:  # 皮卡
                        custom_color = (255, 128, 128)  # 浅蓝色
                    elif cls_id == 7:  # 特种车辆
                        custom_color = (0, 165, 255)  # 橙色
                    elif cls_id == 8:  # 车牌
                        custom_color = (255, 0, 0)  # 蓝色
                    elif cls_id == 9:  # 事故
                        custom_color = (0, 0, 255)  # 红色
                    elif cls_id == 10:  # 违章停车
                        custom_color = (0, 140, 255)  # 橙色
                    elif cls_id == 11:  # 超速
                        custom_color = (0, 0, 200)  # 暗红色
                        
                    # 如果是车辆，并且颜色识别可用，使用车辆颜色
                    if box_type == "vehicle" and cls_id < 8 and "vehicle_rgb" in detection:
                        # 检查配置选项
                        use_class_color = True  # 默认使用类别颜色
                        # 尝试从全局配置中获取
                        try:
                            # 动态导入避免循环导入
                            import sys
                            if 'detection' in sys.modules and hasattr(sys.modules['detection'], 'CONFIG'):
                                use_class_color = sys.modules['detection'].CONFIG.get('use_class_color', True)
                        except:
                            pass  # 出错时使用默认值
                            
                        if not use_class_color:
                            rgb = detection["vehicle_rgb"]
                            # 转换RGB到BGR
                            custom_color = (int(rgb[2]), int(rgb[1]), int(rgb[0]))
                    
                    draw_fancy_box(result_image, x1, y1, x2, y2, box_type=box_type, custom_color=custom_color)
                    
                    # 绘制标签
                    label_text = f"{class_name} ({conf:.2f})"
                    if 'plate_text' in detection:
                        label_text = f"{detection['plate_text']} ({detection['plate_conf']:.2f})"
                    
                    # 根据对象类型选择文字颜色
                    if box_type == "vehicle":
                        text_color = (50, 255, 50)  # 车辆：亮绿色
                    elif box_type == "license_plate":
                        text_color = (255, 255, 0)  # 车牌：黄色
                    elif box_type == "accident":
                        text_color = (0, 165, 255)  # 事故：橙色
                    elif box_type in ["illegal_parking", "overspeed", "violation"]:
                        text_color = (0, 0, 255)    # 违章：红色
                    else:
                        text_color = (255, 255, 255)  # 其他：白色
                    
                    # 绘制文本
                    result_image = draw_text_pil(
                        result_image,
                        label_text,
                        (x1, max(y1-30, 10)),
                        font_size=20,
                        text_color=text_color,
                        bg_color=(0, 0, 0, 180),
                        with_background=True
                    )
                    
                    # 添加到检测结果列表
                    all_detections.append(detection)
        except Exception as e:
            print(f"检测失败: {e}")
            import traceback
            traceback.print_exc()
            
        return result_image, all_detections
        
    def _determine_box_type(self, cls_id):
        """根据类别ID确定边界框类型"""
        if cls_id < 8:  # 车辆类别
            return "vehicle"
        elif cls_id == 8:  # 车牌
            return "license_plate"
        elif cls_id == 9:  # 事故
            return "accident"
        elif cls_id == 10:  # 违停
            return "illegal_parking"
        elif cls_id == 11:  # 超速
            return "overspeed"
        else:
            return "other"
            
    def _recognize_license_plate(self, image, box):
        """
        识别车牌文字
        
        参数:
            image: 原始图像
            box: 车牌框 [x1, y1, x2, y2]
            
        返回:
            plate_text: 识别的车牌文本
            confidence: 置信度
        """
        if self.plate_ocr is None or not self.plate_ocr.is_available():
            return None, 0
            
        # 生成缓存键
        cache_key = hashlib.md5(np.array(box).tobytes() + image[box[1]:box[3], box[0]:box[2]].tobytes()).hexdigest()
        
        # 检查缓存
        if cache_key in self.recognition_cache:
            return self.recognition_cache[cache_key]
            
        # 调用OCR引擎识别车牌
        try:
            result = self.plate_ocr.recognize_plate(image, box)
            
            # 缓存结果
            if result:
                plate_text, confidence = result
                self.recognition_cache[cache_key] = (plate_text, confidence)
                return plate_text, confidence
                
        except Exception as e:
            print(f"车牌识别失败: {e}")
            
        return None, 0
        
    def detect_license_plate(self, image, conf_threshold=None):
        """
        专门检测车牌
        
        参数:
            image: 输入图像
            conf_threshold: 置信度阈值
            
        返回:
            result_image: 标注后的图像
            detections: 车牌检测结果
        """
        result_image, detections = self.detect_objects(
            image, 
            conf_threshold=conf_threshold, 
            detect_vehicles=False, 
            detect_plates=True, 
            detect_accidents=False, 
            detect_violations=False
        )
        return result_image, detections
        
    def detect_accident(self, image, conf_threshold=None):
        """
        专门检测事故
        
        参数:
            image: 输入图像
            conf_threshold: 置信度阈值
            
        返回:
            result_image: 标注后的图像
            detections: 事故检测结果
        """
        result_image, detections = self.detect_objects(
            image, 
            conf_threshold=conf_threshold, 
            detect_vehicles=True,  # 事故检测需要同时检测车辆
            detect_plates=False, 
            detect_accidents=True, 
            detect_violations=False
        )
        return result_image, detections
        
    def detect_violation(self, image, conf_threshold=None, detect_illegal_parking=True, detect_overspeed=True):
        """
        专门检测违章行为
        
        参数:
            image: 输入图像
            conf_threshold: 置信度阈值
            detect_illegal_parking: 是否检测违停
            detect_overspeed: 是否检测超速
            
        返回:
            result_image: 标注后的图像
            detections: 违章检测结果
        """
        # 确定需要检测的类别
        classes_to_detect = []
        if detect_illegal_parking:
            classes_to_detect.append(10)  # 违停类别
        if detect_overspeed:
            classes_to_detect.append(11)  # 超速类别
            
        # 如果没有启用任何违章检测，直接返回
        if not classes_to_detect:
            return image.copy(), []
            
        # 执行检测
        result_image = image.copy()
        all_detections = []
        
        try:
            # 对ONNX模型需要特殊处理，在predict时指定设备
            if hasattr(self, 'is_onnx') and self.is_onnx:
                results = self.model.predict(
                    source=image, 
                    conf=conf_threshold or self.conf_threshold, 
                    classes=classes_to_detect, 
                    device=self.device,
                    verbose=False
                )
            else:
                # 使用常规方式处理PT模型
                results = self.model(image, conf=conf_threshold or self.conf_threshold, 
                                classes=classes_to_detect, verbose=False)
            
            # 处理检测结果
            for r in results:
                boxes = r.boxes
                
                for box in boxes:
                    # 获取边界框
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    
                    # 获取置信度
                    conf = float(box.conf[0])
                    
                    # 获取类别
                    cls_id = int(box.cls[0])
                    class_name = get_vehicle_class_name(cls_id, self.use_chinese, 
                                                       self.classes, self.class_names_zh)
                    
                    # 确定违章类型
                    violation_type = "illegal_parking" if cls_id == 10 else "overspeed"
                    
                    # 创建检测结果字典
                    detection = {
                        "coordinates": [x1, y1, x2, y2],
                        "confidence": conf,
                        "class_id": cls_id,
                        "class_name": class_name,
                        "type": violation_type
                    }
                    
                    # 绘制边界框
                    draw_fancy_box(result_image, x1, y1, x2, y2, box_type=violation_type)
                    
                    # 绘制标签
                    label_text = f"{class_name} ({conf:.2f})"
                    
                    # 根据对象类型选择文字颜色
                    if violation_type == "vehicle":
                        text_color = (50, 255, 50)  # 车辆：亮绿色
                    elif violation_type == "license_plate":
                        text_color = (255, 255, 0)  # 车牌：黄色
                    elif violation_type == "accident":
                        text_color = (0, 165, 255)  # 事故：橙色
                    elif violation_type in ["illegal_parking", "overspeed", "violation"]:
                        text_color = (0, 0, 255)    # 违章：红色
                    else:
                        text_color = (255, 255, 255)  # 其他：白色
                    
                    # 绘制文本
                    result_image = draw_text_pil(
                        result_image,
                        label_text,
                        (x1, max(y1-30, 10)),
                        font_size=20,
                        text_color=text_color,
                        bg_color=(0, 0, 0, 180),
                        with_background=True
                    )
                    
                    # 添加到检测结果列表
                    all_detections.append(detection)
                    
        except Exception as e:
            print(f"违章检测失败: {e}")
            
        return result_image, all_detections
        
    def process_video(self, video_path, output_path=None, enable_license_plate=True, enable_speed=False,
                     show_preview=False, skip_frames=2, timestamp_format='%Y-%m-%d %H:%M:%S',
                     start_time=None, fps_override=None, batch_size=4):
        """
        处理视频文件，检测车辆、车牌和违章行为
        
        参数:
            video_path: 视频文件路径或视频流URL
            output_path: 输出视频路径，如果为None则自动生成
            enable_license_plate: 是否启用车牌检测
            enable_speed: 是否启用速度检测
            show_preview: 是否显示处理预览
            skip_frames: 处理时跳过的帧数
            timestamp_format: 时间戳格式
            start_time: 起始时间，用于自定义时间戳
            fps_override: 覆盖视频的FPS设置
            batch_size: 批处理大小
            
        返回:
            output_path: 处理后的视频路径
            processing_results: 处理结果
        """
        # 导入视频处理器模块
        from .video_processor import process_video as video_processor
        
        # 调用视频处理函数
        return video_processor(
            video_path=video_path,
            output_path=output_path,
            detector=self,
            enable_license_plate=enable_license_plate,
            enable_speed=enable_speed,
            show_preview=show_preview,
            skip_frames=skip_frames,
            timestamp_format=timestamp_format,
            start_time=start_time,
            fps_override=fps_override,
            batch_size=batch_size
        )


def get_detector(model_path, device='cpu', conf_threshold=0.4, classes_file=None):
    """
    创建并返回检测器实例的便捷函数
    
    参数:
        model_path: 模型路径
        device: 运行设备
        conf_threshold: 置信度阈值
        classes_file: 类别文件路径
        
    返回:
        Detector实例
    """
    return Detector(
        model_path=model_path, 
        device=device, 
        conf_threshold=conf_threshold,
        classes_file=classes_file
    )
        
