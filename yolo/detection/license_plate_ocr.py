"""
车牌OCR识别模块

此模块提供车牌文字识别功能，支持中国车牌的识别。
"""

import os
import cv2
import numpy as np
import time
from pathlib import Path
try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

try:
    from paddleocr import PaddleOCR
    HAS_PADDLE = True
except ImportError:
    HAS_PADDLE = False

# 导入工具函数
from .utils import preprocess_license_plate, format_license_plate

# 识别车牌颜色
def identify_plate_color(plate_img):
    """
    识别车牌颜色
    参数:
        plate_img: 车牌图像区域
    返回:
        plate_color: 车牌颜色名称
        bg_color: 车牌背景颜色(BGR格式)
    """
    if plate_img is None or plate_img.size == 0:
        return "未知", (0, 0, 0)
        
    # 转换为HSV色彩空间
    hsv_img = cv2.cvtColor(plate_img, cv2.COLOR_BGR2HSV)
    
    # 统计主要颜色
    h_hist = cv2.calcHist([hsv_img], [0], None, [180], [0, 180])
    s_hist = cv2.calcHist([hsv_img], [1], None, [256], [0, 256])
    v_hist = cv2.calcHist([hsv_img], [2], None, [256], [0, 256])
    
    # 获取主要色调
    h_dominant = np.argmax(h_hist)
    s_dominant = np.argmax(s_hist)
    v_dominant = np.argmax(v_hist)
    
    # 基于HSV判断颜色
    if s_dominant < 50:  # 低饱和度
        if v_dominant > 200:
            return "白色", (255, 255, 255)
        elif v_dominant > 120:
            return "灰色", (120, 120, 120)
        else:
            return "黑色", (0, 0, 0)
    
    elif h_dominant >= 90 and h_dominant <= 140:
        return "蓝色", (255, 0, 0)
    elif h_dominant >= 35 and h_dominant <= 80:
        return "绿色", (0, 255, 0)
    elif h_dominant >= 0 and h_dominant <= 20:
        return "红色", (0, 0, 255)
    elif h_dominant >= 20 and h_dominant <= 35:
        return "黄色", (0, 255, 255)
    else:
        return "其他", (128, 128, 128)

# 添加中文车牌字符修复函数
def fix_chinese_plate_text(text):
    """修复常见的中文车牌字符识别问题"""
    # 常见中文省份简称映射
    province_map = {
        '京': ['京', '景', '东', '束'],
        '津': ['津', '宋'],
        '冀': ['冀', '养'],
        '晋': ['晋', '陕'],
        '蒙': ['蒙', '豪'],
        '辽': ['辽', '辽'],
        '吉': ['吉', '语'],
        '黑': ['黑', '黎'],
        '沪': ['沪', '记'],
        '苏': ['苏', '苏'],
        '浙': ['浙', '泜', '浃'],
        '皖': ['皖', '院', '完', '晥', '浣'],  # 添加更多可能被误识别为"皖"的字符
        '闽': ['闽', '闵'],
        '赣': ['赣', '感'],
        '鲁': ['鲁', '录'],
        '豫': ['豫', '预'],
        '鄂': ['鄂', '郭'],
        '湘': ['湘', '相'],
        '粤': ['粤', '类'],
        '桂': ['桂', '柱'],
        '琼': ['琼', '球'],
        '渝': ['渝', '渔'],
        '川': ['川', '州'],
        '贵': ['贵', '贯'],
        '云': ['云', '去'],
        '藏': ['藏', '戌'],
        '陕': ['陕', '晋'],
        '甘': ['甘', '甲'],
        '青': ['青', '清'],
        '宁': ['宁', '守'],
        '新': ['新', '亲']
    }
    
    # 尝试判断第一个字符是否为省份简称
    if text and len(text) > 0:
        first_char = text[0]
        # 如果第一个字符不在省份映射中，尝试猜测正确的省份
        if first_char not in province_map:
            # 检查是否是"皖"字，其他省份也可以加入类似处理
            if any(c in text for c in ['?', '啊', '院', '完', 'W', '浣', '垸']):
                # "皖"字常被错误识别为这些字符
                text = '皖' + text[1:]
    
    # 处理中间的点号
    text = text.replace('·', '·').replace('．', '·').replace('。', '·').replace('口', '·')
    
    # 规范车牌号格式（如果没有点号但有字母与数字混合，插入点号）
    if '·' not in text and len(text) >= 3:
        for i in range(1, len(text)-1):
            if (text[i].isalpha() and text[i+1].isdigit()) or (text[i].isdigit() and text[i+1].isalpha()):
                text = text[:i+1] + '·' + text[i+1:]
                break
    
    return text

class LicensePlateOCR:
    """
    车牌OCR识别器类
    支持使用PaddleOCR识别车牌
    """
    
    def __init__(self, use_gpu=False, lang='ch', use_angle_cls=True):
        """
        初始化车牌OCR识别器
        
        参数:
            use_gpu: 是否使用GPU加速
            lang: 语言，默认为中文
            use_angle_cls: 是否使用文字方向分类
        """
        self.use_gpu = use_gpu and HAS_TORCH and torch.cuda.is_available()
        self.ocr_engine = None
        self.engine_name = "未初始化"
        
        try:
            if HAS_PADDLE:
                self.ocr_engine = PaddleOCR(
                    use_angle_cls=use_angle_cls,
                    lang=lang,
                    use_gpu=self.use_gpu,
                    show_log=False
                )
                self.engine_name = "PaddleOCR"
                print(f"已加载PaddleOCR引擎，使用GPU: {self.use_gpu}")
            else:
                print("警告: 未找到PaddleOCR，OCR功能不可用")
        except Exception as e:
            print(f"OCR引擎初始化失败: {e}")
            self.ocr_engine = None
    
    def is_available(self):
        """
        检查OCR引擎是否可用
        
        返回:
            bool: 是否可用
        """
        return self.ocr_engine is not None
    
    def get_engine_info(self):
        """
        获取OCR引擎信息
        
        返回:
            str: 引擎信息字符串
        """
        device = "GPU" if self.use_gpu else "CPU"
        return f"{self.engine_name} ({device})"
    
    def recognize_plate(self, image, box, min_confidence=0.3):
        """
        识别车牌文字
        
        参数:
            image: 原始图像
            box: 车牌框 [x1, y1, x2, y2]
            min_confidence: 最小置信度
            
        返回:
            (plate_text, confidence): 车牌文本和置信度
        """
        if not self.is_available():
            return "未知", 0.0
            
        try:
            # 提取车牌区域
            x1, y1, x2, y2 = map(int, box)
            
            # 边界检查
            if x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1:
                return "无效边界", 0.0
                
            # 防止越界
            h, w = image.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            
            # 检查裁剪区域是否有效
            if x2 <= x1 or y2 <= y1 or (x2-x1) < 10 or (y2-y1) < 5:
                return "区域过小", 0.0
                
            plate_img = image[y1:y2, x1:x2]
            
            if plate_img is None or plate_img.size == 0:
                return "无效图像", 0.0
                
            # 尝试多种预处理方法以提高识别率
            result = None
            best_confidence = 0.0
            best_text = None
            
            # 使用原始图像进行识别
            ocr_result = self.ocr_engine.ocr(plate_img, cls=True)
            
            # 处理OCR结果
            if ocr_result is not None and len(ocr_result) > 0:
                for idx, line_result in enumerate(ocr_result):
                    # 检查结果是否为空
                    if line_result is None or len(line_result) == 0:
                        continue
                        
                    for line in line_result:
                        # 确保行数据格式正确
                        if not isinstance(line, list) or len(line) < 2:
                            continue
                            
                        # 确保结果包含文本和置信度
                        text_conf = line[1]
                        if not isinstance(text_conf, tuple) or len(text_conf) < 2:
                            continue
                            
                        text, confidence = text_conf
                        
                        # 验证文本和置信度
                        if not text or not isinstance(confidence, (int, float)):
                            continue
                            
                        # 更新最佳结果
                        if confidence > best_confidence and len(text) >= 4:
                            best_text = text
                            best_confidence = confidence
            
            # 如果原始图像识别失败，尝试增强处理
            if best_confidence < min_confidence:
                try:
                    # 增强对比度
                    enhanced_img = cv2.convertScaleAbs(plate_img, alpha=1.5, beta=0)
                    ocr_result = self.ocr_engine.ocr(enhanced_img, cls=True)
                    
                    # 处理OCR结果
                    if ocr_result is not None and len(ocr_result) > 0:
                        for idx, line_result in enumerate(ocr_result):
                            # 检查结果是否为空
                            if line_result is None or len(line_result) == 0:
                                continue
                                
                            for line in line_result:
                                # 确保行数据格式正确
                                if not isinstance(line, list) or len(line) < 2:
                                    continue
                                    
                                # 确保结果包含文本和置信度
                                text_conf = line[1]
                                if not isinstance(text_conf, tuple) or len(text_conf) < 2:
                                    continue
                                    
                                text, confidence = text_conf
                                
                                # 验证文本和置信度
                                if not text or not isinstance(confidence, (int, float)):
                                    continue
                                    
                                # 更新最佳结果
                                if confidence > best_confidence and len(text) >= 4:
                                    best_text = text
                                    best_confidence = confidence
                except Exception as enhance_err:
                    print(f"图像增强处理失败: {enhance_err}")
            
            # 处理最终结果
            if best_text and best_confidence >= min_confidence:
                # 修复车牌文本
                fixed_text = fix_chinese_plate_text(best_text)
                return fixed_text, float(best_confidence)
                
            return "未识别", 0.0
            
        except Exception as e:
            print(f"车牌识别失败: {e}")
            return "识别错误", 0.0

def get_license_plate_ocr(use_gpu=None):
    """
    创建并返回车牌OCR识别器实例
    
    参数:
        use_gpu: 是否使用GPU加速
    
    返回:
        LicensePlateOCR: OCR识别器实例
    """
    # 如果未指定use_gpu，则根据全局设置决定是否使用GPU
    if use_gpu is None:
        import torch
        use_gpu = torch.cuda.is_available()
        
    return LicensePlateOCR(use_gpu=use_gpu) 