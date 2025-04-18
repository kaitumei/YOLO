import cv2
import numpy as np
import os
import time
import logging
import glob
import math
import json
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO
import matplotlib.pyplot as plt
import matplotlib
import torch
import threading
import base64

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("集成检测系统")

# 解决 Matplotlib 中文乱码
matplotlib.rcParams['font.sans-serif'] = ['SimHei']  # 黑体
matplotlib.rcParams['axes.unicode_minus'] = False    # 解决负号显示问题

# 创建结果存储目录
def create_directories():
    """创建存储结果的目录"""
    directories = ["detection_results", "speed_results", "integrated_results"]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
    
    # 创建超速车辆子目录
    os.makedirs("speed_results/exceeded", exist_ok=True)
    
    # 初始化速度记录文件
    speed_record_file = "speed_results/SpeedRecord.txt"
    with open(speed_record_file, "w") as file:
        file.write("ID \t SPEED\n------\t-------\n")
    
    return speed_record_file

# 加载配置文件
def load_config(config_path="detector_config.json"):
    """从JSON文件加载检测器配置"""
    default_config = {
        "speed_limit": 80,
        "conf_threshold": 0.4,
        "iou_threshold": 0.5,
        "enhance_level": 1,
        "debug": False,
        "model_paths": ["models/*.onnx", "*.onnx", "../models/*.onnx"]
    }
    
    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                logger.info(f"已加载配置文件: {config_path}")
                # 合并配置，使用加载的值，缺失项使用默认值
                for key in default_config:
                    if key not in config:
                        config[key] = default_config[key]
                return config
    except Exception as e:
        logger.error(f"加载配置文件出错: {e}")
    
    logger.info("使用默认配置")
    return default_config

# 速度记录文件路径
SPEED_RECORD_FILE = create_directories()
# 加载配置
CONFIG = load_config()

# 欧氏距离跟踪器类 - 来自tracker2.py
class EuclideanDistTracker:
    def __init__(self, speed_limit=None):
        # 从配置获取速度限制
        self.speed_limit = speed_limit if speed_limit else CONFIG["speed_limit"]
        
        # 目标跟踪相关属性
        self.center_points = {}  # 存储目标中心点坐标 {id: (cx, cy)}
        self.id_count = 0  # 自增ID计数器

        # 速度计算相关属性
        self.et = 0  # 经过时间
        self.s1 = np.zeros((1, 1000))  # 进入检测线时间记录
        self.s2 = np.zeros((1, 1000))  # 离开检测线时间记录
        self.s = np.zeros((1, 1000))  # 时间差存储

        # 状态标记
        self.f = np.zeros(1000)  # 抓拍触发标记
        self.capf = np.zeros(1000)  # 已抓拍标记

        # 统计计数器
        self.count = 0  # 总车辆计数
        self.exceeded = 0  # 超速车辆计数

    def update(self, objects_rect):
        """核心更新方法，处理目标检测框并跟踪"""
        objects_bbs_ids = []

        # 遍历每个检测到的目标框
        for rect in objects_rect:
            x, y, w, h = rect
            cx = (x + x + w) // 2  # 计算中心点x坐标
            cy = (y + y + h) // 2  # 计算中心点y坐标

            # 目标匹配标识
            same_object_detected = False

            # 遍历现有目标进行匹配
            for id, pt in self.center_points.items():
                # 计算欧氏距离（新旧中心点间距）
                dist = math.hypot(cx - pt[0], cy - pt[1])

                # 匹配成功条件（距离小于阈值）
                if dist < 70:
                    self.center_points[id] = (cx, cy)  # 更新中心点
                    objects_bbs_ids.append([x, y, w, h, id])
                    same_object_detected = True

                    # 速度检测线逻辑（上方检测线范围410-430）
                    if 410 <= cy <= 430:
                        self.s1[0, id] = time.time()  # 记录进入时间

                    # 下方检测线范围235-255
                    if 235 <= cy <= 255:
                        self.s2[0, id] = time.time()  # 记录离开时间
                        self.s[0, id] = self.s2[0, id] - self.s1[0, id]  # 计算时间差

                    # 触发抓拍条件（车辆完全通过检测区域）
                    if cy < 235:
                        self.f[id] = 1  # 设置抓拍标志

            # 新目标处理
            if not same_object_detected:
                self.center_points[self.id_count] = (cx, cy)
                objects_bbs_ids.append([x, y, w, h, self.id_count])
                # 初始化新目标的计时器
                self.id_count += 1
                self.s[0, self.id_count] = 0
                self.s1[0, self.id_count] = 0
                self.s2[0, self.id_count] = 0

        # 清理无效目标
        new_center_points = {}
        for obj_bb_id in objects_bbs_ids:
            _, _, _, _, object_id = obj_bb_id
            new_center_points[object_id] = self.center_points[object_id]
        self.center_points = new_center_points.copy()

        return objects_bbs_ids

    def getsp(self, id):
        """速度计算方法：固定距离/时间差"""
        if self.s[0, id] != 0:
            s = 214.15 / self.s[0, id]  # 214.15为校准参数（单位转换系数）
        else:
            s = 0
        return int(s)

    def capture(self, img, x, y, h, w, sp, id):
        """超速抓拍方法"""
        if self.capf[id] == 0:  # 防止重复抓拍
            self.capf[id] = 1  # 设置已抓拍标记
            self.f[id] = 0  # 重置触发标记

            # 检查边界并截取车辆区域
            img_height, img_width = img.shape[:2]
            y1 = max(0, y - 5)
            y2 = min(img_height, y + h + 5)
            x1 = max(0, x - 5)
            x2 = min(img_width, x + w + 5)
            crop_img = img[y1:y2, x1:x2]

            # 生成文件名
            n = f"{id}_speed_{sp}"
            file = f"speed_results/{n}.jpg"

            # 保存图片
            cv2.imwrite(file, crop_img)
            self.count += 1  # 总计数增加

            # 记录到文件
            with open(SPEED_RECORD_FILE, "a") as filet:
                if sp > self.speed_limit:
                    # 超速车辆特殊处理
                    file2 = f"speed_results/exceeded/{n}.jpg"
                    cv2.imwrite(file2, crop_img)
                    filet.write(f"{id} \t {sp}<---exceeded\n")
                    self.exceeded += 1
                else:
                    filet.write(f"{id} \t {sp}\n")

    def limit(self):
        """获取速度限制"""
        return self.speed_limit

    def end(self):
        """生成统计报告"""
        with open(SPEED_RECORD_FILE, "a") as file:
            file.write("\n-------------\nSUMMARY\n-------------\n")
            file.write(f"Total Vehicles :\t{self.count}\n")
            file.write(f"Exceeded speed limit :\t{self.exceeded}")

# 图像预处理函数 - 来自pictureOCR.py
def preprocess_image(image, enhance_level=1):
    """
    增强的图像预处理，支持多种增强级别
    enhance_level: 0=最小处理, 1=标准处理, 2=强化处理
    """
    logger.debug(f"预处理图像，增强级别: {enhance_level}")
    original_shape = image.shape
    
    # 调整图像大小，保持纵横比
    max_size = 1280
    height, width = image.shape[:2]
    scale = min(max_size / width, max_size / height)
    
    if scale < 1:
        new_width, new_height = int(width * scale), int(height * scale)
        image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
        logger.debug(f"调整图像大小: {width}x{height} -> {new_width}x{new_height}")
    
    if enhance_level >= 1:
        # 标准处理 - 对比度增强
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        lab = cv2.merge((l, a, b))
        image = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    
    if enhance_level >= 2:
        # 强化处理 - 锐化和降噪
        # 使用双边滤波进行降噪同时保留边缘
        image = cv2.bilateralFilter(image, 9, 75, 75)
        
        # 锐化处理
        kernel = np.array([[-1,-1,-1], 
                           [-1, 9,-1],
                           [-1,-1,-1]])
        image = cv2.filter2D(image, -1, kernel)
        
        # 再次应用CLAHE以增强对比度
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        lab = cv2.merge((l, a, b))
        image = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    
    logger.debug(f"预处理后图像形状: {image.shape}")
    return image

# 车牌检测和绘制函数 - 来自pictureOCR.py
def detect_license_plates(image, model, conf_thres=0.4, iou_thres=0.5):
    """
    使用YOLO模型检测车牌，返回检测结果和置信度
    """
    logger.debug(f"开始车牌检测，参数: conf={conf_thres}, iou={iou_thres}")
    start_time = time.time()
    results = model(image, conf=conf_thres, iou=iou_thres)
    detection_time = time.time() - start_time
    
    boxes = results[0].boxes.xyxy
    confidences = results[0].boxes.conf
    
    logger.info(f"检测完成，用时: {detection_time:.2f}秒，找到 {len(boxes)} 个车牌")
    return boxes, confidences, detection_time

# PIL中文文本绘制函数 - 增强版，来自pictureOCR.py
def draw_fancy_text(img, text, position, font_size=36, text_color=(255, 255, 255), bg_color=(0, 120, 0), add_shadow=True, confidence=None):
    """
    使用PIL绘制美化的中文文本到OpenCV图像上，带阴影、渐变背景和圆角效果
    """
    # OpenCV图像转为PIL图像
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    
    # 选择字体，使用系统中文字体
    try:
        # 尝试使用系统中文字体
        if os.path.exists('C:/Windows/Fonts/simhei.ttf'):  # Windows系统
            font = ImageFont.truetype('C:/Windows/Fonts/simhei.ttf', font_size)
        elif os.path.exists('/usr/share/fonts/truetype/wqy/wqy-microhei.ttc'):  # Linux系统
            font = ImageFont.truetype('/usr/share/fonts/truetype/wqy/wqy-microhei.ttc', font_size)
        else:
            # 尝试使用默认字体
            font = ImageFont.load_default()
            logger.warning("警告: 找不到合适的中文字体，使用默认字体!")
    except Exception as e:
        logger.warning(f"加载字体出错: {e}, 使用默认字体")
        font = ImageFont.load_default()
    
    # 根据置信度调整背景颜色
    if confidence is not None:
        # 红色到绿色的渐变
        green = int(120 * confidence * 1.5)  # 最高到180
        red = int(120 * (1 - confidence) * 1.5)  # 最高到180
        bg_color = (red, green, 0)
    
    # 获取文本大小
    text_size = draw.textbbox((0, 0), text, font=font)[2:]
    padding = 10  # 文本周围的填充
    
    # 创建一个透明的图层用于绘制圆角矩形和文本
    overlay = Image.new('RGBA', img_pil.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    
    # 计算矩形位置
    x, y = position
    rect_x1 = x - padding
    rect_y1 = y - padding
    rect_x2 = x + text_size[0] + padding
    rect_y2 = y + text_size[1] + padding
    
    # 绘制圆角矩形背景 - 使用渐变色
    for i in range(rect_y1, rect_y2):
        ratio = (i - rect_y1) / (rect_y2 - rect_y1)
        # 从顶部的深绿色到底部的较亮绿色
        r = int(bg_color[0] * (1 - ratio) + min(bg_color[0] + 50, 255) * ratio)
        g = int(bg_color[1] * (1 - ratio) + min(bg_color[1] + 50, 255) * ratio)
        b = int(bg_color[2] * (1 - ratio) + min(bg_color[2] + 50, 255) * ratio)
        
        overlay_draw.line([(rect_x1, i), (rect_x2, i)], fill=(r, g, b, 220))
    
    # 添加边框
    for i in range(3):  # 3像素宽的边框
        overlay_draw.rectangle(
            [rect_x1+i, rect_y1+i, rect_x2-i, rect_y2-i], 
            outline=(255, 255, 255, 150), 
            width=1
        )
    
    # 如果启用阴影，绘制文本阴影
    if add_shadow:
        shadow_offset = 2
        overlay_draw.text(
            (x + shadow_offset, y + shadow_offset), 
            text, 
            font=font, 
            fill=(0, 0, 0, 160)
        )
    
    # 绘制文本
    overlay_draw.text((x, y), text, font=font, fill=text_color)
    
    # 合并图层
    img_pil = Image.alpha_composite(img_pil.convert('RGBA'), overlay)
    
    # PIL图像转回OpenCV图像
    return cv2.cvtColor(np.array(img_pil.convert('RGB')), cv2.COLOR_RGB2BGR)

# 集成类，整合车牌检测和速度监测功能
class IntegratedDetector:
    def __init__(self, license_plate_model_path=None, debug=False):
        """初始化集成检测器"""
        self.debug = debug
        self.license_plate_model = None
        self.tracker = EuclideanDistTracker(speed_limit=CONFIG["speed_limit"])
        self.model_lock = threading.Lock()
        
        # 加载车牌检测模型
        if license_plate_model_path:
            self.load_license_plate_model(license_plate_model_path)
        else:
            # 尝试自动查找模型
            self.auto_find_model()
        
        # 初始化背景减除器（用于速度检测）
        self.fgbg = cv2.createBackgroundSubtractorMOG2(detectShadows=True)
        
        # 形态学操作的核
        self.kernalOp = np.ones((3,3), np.uint8)
        self.kernalOp2 = np.ones((5,5), np.uint8)
        self.kernalCl = np.ones((11,11), np.uint8)
        self.kernal_e = np.ones((5,5), np.uint8)
        
        logger.info("集成检测器初始化完成")

    def auto_find_model(self):
        """自动查找车牌检测模型"""
        # 可能的模型路径
        search_paths = CONFIG["model_paths"]
        
        for path_pattern in search_paths:
            model_files = glob.glob(path_pattern)
            if model_files:
                logger.info(f"自动找到模型: {model_files[0]}")
                self.load_license_plate_model(model_files[0])
                return
                
        logger.warning("未找到车牌检测模型文件，将无法进行车牌检测")

    def load_license_plate_model(self, model_path):
        """加载车牌检测模型"""
        try:
            if not os.path.exists(model_path):
                logger.error(f"模型文件不存在: {model_path}")
                return False
                
            logger.info(f"加载车牌检测模型: {model_path}")
            
            # 检测GPU可用性并选择设备
            if torch.cuda.is_available():
                device = "cuda:0"
                gpu_name = torch.cuda.get_device_name(0)
                logger.info(f"使用GPU: {gpu_name}")
            else:
                device = "cpu"
                logger.info("使用CPU进行推理")
            
            # 加载模型到指定设备    
            self.license_plate_model = YOLO(model_path).to(device)
            logger.info("车牌检测模型加载完成")
            return True
            
        except Exception as e:
            logger.error(f"加载车牌检测模型出错: {e}")
            self.license_plate_model = None
            return False

    def detect_license_plate(self, image, conf_threshold=0.4, iou_threshold=0.5):
        """检测图像中的车牌"""
        if self.license_plate_model is None:
            logger.error("车牌检测模型未加载，无法进行检测")
            return image.copy(), [], []
        
        try:
            # 图像预处理
            preprocessed_image = preprocess_image(image, enhance_level=CONFIG["enhance_level"])
            
            # 车牌检测
            with self.model_lock:
                boxes, confidences, detection_time = detect_license_plates(
                    preprocessed_image, 
                    self.license_plate_model, 
                    conf_thres=conf_threshold, 
                    iou_thres=iou_threshold
                )
            
            # 验证检测结果
            valid_boxes, valid_confidences = self.validate_detection(boxes, confidences, preprocessed_image.shape)
            
            # 仅在有有效检测时绘制结果
            if valid_boxes:
                result_image = preprocessed_image.copy()
                for i, (box, conf) in enumerate(zip(valid_boxes, valid_confidences)):
                    x1, y1, x2, y2 = map(int, box)
                    
                    # 绘制边框
                    cv2.rectangle(result_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    
                    # 添加文本标签
                    text = f"车牌 {conf:.2f}"
                    result_image = draw_fancy_text(
                        result_image, 
                        text, 
                        (x1, y1 - 30), 
                        font_size=20,
                        confidence=float(conf)
                    )
            else:
                result_image = preprocessed_image.copy()
                
            return result_image, valid_boxes, valid_confidences
            
        except Exception as e:
            logger.error(f"车牌检测失败: {e}")
            return image.copy(), [], []

    def detect_speed(self, frame, roi_coords=None):
        """检测视频帧中的车辆速度"""
        if roi_coords is None:
            # 默认ROI区域 (50:540, 200:960)
            roi_coords = (50, 540, 200, 960)
        
        # 提取ROI区域
        roi = frame[roi_coords[0]:roi_coords[1], roi_coords[2]:roi_coords[3]]
        
        # 运动检测
        fgmask = self.fgbg.apply(roi)
        _, imBin = cv2.threshold(fgmask, 200, 255, cv2.THRESH_BINARY)
        mask1 = cv2.morphologyEx(imBin, cv2.MORPH_OPEN, self.kernalOp)
        mask2 = cv2.morphologyEx(mask1, cv2.MORPH_CLOSE, self.kernalCl)
        e_img = cv2.erode(mask2, self.kernal_e)
        
        # 轮廓检测
        contours, _ = cv2.findContours(e_img, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        detections = []
        
        # 筛选有效轮廓
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > 1000:  # 面积阈值过滤小目标
                x, y, w, h = cv2.boundingRect(cnt)
                detections.append([x, y, w, h])
        
        # 目标跟踪
        boxes_ids = self.tracker.update(detections)
        
        # 绘制结果
        result_roi = roi.copy()
        for box_id in boxes_ids:
            x, y, w, h, id = box_id
            speed = self.tracker.getsp(id)
            
            # 根据速度显示不同颜色
            if speed < self.tracker.limit():  # 正常速度
                cv2.putText(result_roi, f"{id} {speed}", (x, y-15), 
                           cv2.FONT_HERSHEY_PLAIN, 1, (255, 255, 0), 2)  # 黄字显示
                cv2.rectangle(result_roi, (x, y), (x + w, y + h), (0, 255, 0), 3)
            else:  # 超速情况
                cv2.putText(result_roi, f"{id} {speed}", (x, y-15),
                           cv2.FONT_HERSHEY_PLAIN, 1, (0, 0, 255), 2)  # 红字显示
                cv2.rectangle(result_roi, (x, y), (x + w, y + h), (0, 165, 255), 3)
            
            # 超速抓拍逻辑
            if self.tracker.f[id] == 1 and speed != 0:
                self.tracker.capture(result_roi, x, y, h, w, speed, id)
        
        # 绘制测速参考线
        line_params = [
            ((0, 410), (960, 410)),  # 上方水平线对
            ((0, 430), (960, 430)),
            ((0, 235), (960, 235)),  # 下方水平线对
            ((0, 255), (960, 255))
        ]
        for (start, end) in line_params:
            cv2.line(result_roi, start, end, (0, 0, 255), 2)  # 红色参考线
        
        # 生成结果图像
        result_frame = frame.copy()
        result_frame[roi_coords[0]:roi_coords[1], roi_coords[2]:roi_coords[3]] = result_roi
        
        return result_frame, boxes_ids

    def validate_detection(self, boxes, confidences, image_shape):
        """
        验证检测结果的有效性
        移除明显错误的检测: 过大、过小或比例不合理的框
        """
        if len(boxes) == 0:
            return [], []
        
        valid_boxes = []
        valid_confidences = []
        img_height, img_width = image_shape[:2]
        img_area = img_height * img_width
        
        for box, conf in zip(boxes, confidences):
            x1, y1, x2, y2 = box.tolist() if isinstance(box, torch.Tensor) else box
            width = x2 - x1
            height = y2 - y1
            
            # 避免除零错误
            if height <= 0 or width <= 0:
                if self.debug:
                    logger.debug(f"跳过无效框: 高度={height}, 宽度={width}")
                continue
                
            box_area = width * height
            aspect_ratio = width / height
            
            # 中国车牌标准宽高比约为3:1
            valid_aspect_ratio = 1.5 < aspect_ratio < 5
            
            # 车牌大小通常占图像面积的0.1%到10%
            valid_size = 0.001 < box_area / img_area < 0.1
            
            if valid_aspect_ratio and valid_size:
                valid_boxes.append([x1, y1, x2, y2])
                valid_confidences.append(conf)
            elif self.debug:
                reason = []
                if not valid_aspect_ratio:
                    reason.append(f"宽高比不合理({aspect_ratio:.2f})")
                if not valid_size:
                    reason.append(f"尺寸不合理({box_area/img_area:.4f})")
                
                logger.debug(f"移除无效检测框: {[x1, y1, x2, y2]} 置信度:{conf:.2f}, 原因: {', '.join(reason)}")
        
        return valid_boxes, valid_confidences

    def process_image(self, image_path_or_array):
        """处理单个图像，检测车牌"""
        if isinstance(image_path_or_array, str):
            # 从文件路径加载图像
            image = cv2.imread(image_path_or_array)
            if image is None:
                logger.error(f"无法读取图像: {image_path_or_array}")
                return None, None, None
        else:
            # 使用提供的图像数组
            image = image_path_or_array
        
        # 检测车牌
        result_image, boxes, confidences = self.detect_license_plate(image)
        
        return result_image, boxes, confidences

    def process_video_frame(self, frame, enable_license_plate=True, enable_speed=True):
        """处理视频帧，结合车牌检测和速度监测"""
        result_frame = frame.copy()
        license_plate_results = None
        speed_results = None
        
        # 车牌检测
        if enable_license_plate and self.license_plate_model is not None:
            license_plate_image, boxes, confidences = self.detect_license_plate(frame)
            if boxes is not None and len(boxes) > 0:
                result_frame = license_plate_image
                license_plate_results = {
                    'boxes': boxes.tolist() if isinstance(boxes, torch.Tensor) else boxes,
                    'confidences': confidences.tolist() if isinstance(confidences, torch.Tensor) else confidences
                }
        
        # 速度检测
        if enable_speed:
            speed_frame, tracked_objects = self.detect_speed(result_frame)
            result_frame = speed_frame
            speed_results = tracked_objects
        
        return result_frame, license_plate_results, speed_results

    def process_video(self, video_path, output_path=None, enable_license_plate=True, enable_speed=True):
        """处理视频文件，结合车牌检测和速度监测"""
        # 打开视频文件
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"无法打开视频文件: {video_path}")
            return False
        
        # 获取视频属性
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # 设置输出路径
        if output_path is None:
            basename = os.path.basename(video_path)
            name, ext = os.path.splitext(basename)
            output_path = f"integrated_results/{name}_processed.mp4"
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # 初始化视频写入器
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        if not out.isOpened():
            logger.error("无法创建输出视频文件")
            return False
        
        frame_count = 0
        processing_results = []
        
        # 处理视频帧
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # 每隔几帧处理一次（降低计算量）
            frame_count += 1
            if frame_count % 2 != 0:  # 每2帧处理一次
                out.write(frame)
                continue
            
            # 处理当前帧
            result_frame, license_plate_results, speed_results = self.process_video_frame(
                frame, 
                enable_license_plate=enable_license_plate, 
                enable_speed=enable_speed
            )
            
            # 将处理结果添加到列表
            frame_result = {
                'frame': frame_count,
                'license_plates': license_plate_results,
                'speed_tracking': speed_results
            }
            processing_results.append(frame_result)
            
            # 写入输出视频
            out.write(result_frame)
            
            # 显示处理进度
            if frame_count % max(1, total_frames//10) == 0:
                logger.info(f"处理进度: {frame_count}/{total_frames} ({frame_count/total_frames*100:.1f}%)")
        
        # 释放资源
        cap.release()
        out.release()
        
        # 生成结束报告
        self.tracker.end()
        
        logger.info(f"视频处理完成，输出文件: {output_path}")
        return output_path, processing_results

    def detect_image_base64(self, image_base64):
        """处理Base64编码的图像，用于API集成"""
        try:
            # 解码Base64图像
            image_data = base64.b64decode(image_base64)
            image = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)
            
            # 检测车牌
            result_image, boxes, confidences = self.detect_license_plate(image)
            
            # 将结果图像编码为Base64
            _, buffer = cv2.imencode('.jpg', result_image)
            result_base64 = base64.b64encode(buffer).decode('utf-8')
            
            # 准备检测结果
            detections = []
            if boxes is not None:
                for i, (box, conf) in enumerate(zip(boxes, confidences)):
                    x1, y1, x2, y2 = map(int, box)
                    detections.append({
                        "class_name": "车牌",
                        "confidence": float(conf),
                        "coordinates": [x1, y1, x2, y2]
                    })
            
            return result_base64, detections
        except Exception as e:
            logger.error(f"Base64图像处理出错: {e}")
            return None, None

# 创建一个单例实例，用于应用程序调用
detector = None

def get_detector(license_plate_model_path=None):
    """获取检测器的单例实例"""
    global detector
    if detector is None:
        detector = IntegratedDetector(license_plate_model_path)
    return detector 