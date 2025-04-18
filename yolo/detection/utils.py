import cv2
import numpy as np
import os
from PIL import Image, ImageDraw, ImageFont

def draw_text_pil(img, text, pos, font_size=24, text_color=(255, 255, 255), bg_color=(0, 0, 255, 128), font_path=None, with_background=False):
    """
    使用PIL绘制支持中文的文本
    
    参数:
        img: OpenCV格式图像
        text: 要绘制的文本
        pos: 文本位置 (x, y)
        font_size: 字体大小
        text_color: 文本颜色 (R, G, B)
        bg_color: 背景颜色 (R, G, B, A)，仅当with_background=True时使用
        font_path: 字体路径，None则使用默认
        with_background: 是否绘制文本背景
        
    返回:
        添加文本后的图像
    """
    # OpenCV图像转PIL图像
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    
    # 创建绘图对象
    draw = ImageDraw.Draw(img_pil, 'RGBA')
    
    # 加载字体，如果没有指定字体，尝试使用系统默认字体
    try:
        if font_path and os.path.exists(font_path):
            font = ImageFont.truetype(font_path, font_size)
        else:
            # 尝试常见中文字体
            font_candidates = [
                os.path.join(os.environ.get('WINDIR', ''), 'Fonts', 'simhei.ttf'),  # Windows
                os.path.join(os.environ.get('WINDIR', ''), 'Fonts', 'msyh.ttc'),    # Windows
                '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf',        # Linux
                '/System/Library/Fonts/PingFang.ttc',                               # macOS
                '/System/Library/Fonts/STHeiti Light.ttc'                           # macOS
            ]
            
            for font_path in font_candidates:
                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, font_size)
                    print(f"使用字体: {font_path}")
                    break
            else:
                # 如果找不到中文字体，使用默认字体
                font = ImageFont.load_default()
                print("使用默认字体，可能不支持中文")
    except Exception as e:
        print(f"加载字体失败: {e}，使用默认字体")
        font = ImageFont.load_default()
    
    # 计算文本大小
    text_width, text_height = draw.textbbox((0, 0), text, font=font)[2:4]
    
    # 如果需要背景，绘制背景矩形
    x, y = pos
    if with_background:
        draw.rectangle(
            [(x, y), (x + text_width + 10, y + text_height + 5)],
            fill=bg_color
        )
    
    # 绘制文本
    draw.text((x + 5 if with_background else x, y), text, fill=text_color, font=font)
    
    # PIL图像转回OpenCV格式
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

def draw_fancy_box(img, x1, y1, x2, y2, thickness=2, alpha=0.2, box_type='vehicle', custom_color=None):
    """
    绘制美观的边界框，支持不同类型的对象使用不同的颜色
    
    参数:
        img: 输入图像
        x1, y1, x2, y2: 边界框坐标
        thickness: 线条粗细
        alpha: 填充透明度 (已弃用，保留参数兼容性)
        box_type: 框类型，可选值: vehicle, license_plate, accident, violation, illegal_parking, overspeed
        custom_color: 自定义颜色，覆盖box_type设置的颜色
        
    返回:
        添加边界框的图像
    """
    # 基于类型设置颜色
    if custom_color:
        color = custom_color
    else:
        if box_type == 'vehicle':
            color = (0, 255, 0)  # 绿色
        elif box_type == 'license_plate':
            color = (255, 0, 0)  # 蓝色 (BGR)
        elif box_type == 'accident':
            color = (0, 0, 255)  # 红色
        elif box_type in ['violation', 'illegal_parking']:
            color = (0, 165, 255)  # 橙色
        elif box_type == 'overspeed':
            color = (0, 0, 255)  # 红色
        else:
            color = (200, 200, 200)  # 灰色
            
    # 确保坐标是整数
    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
    
    # 画矩形边框
    cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)
    
    # 添加小装饰(边角线)
    corner_length = min(30, (x2-x1)//3, (y2-y1)//3)  # 不超过边长的1/3
    
    # 左上角
    cv2.line(img, (x1, y1), (x1 + corner_length, y1), color, thickness + 1)
    cv2.line(img, (x1, y1), (x1, y1 + corner_length), color, thickness + 1)
    
    # 右上角
    cv2.line(img, (x2, y1), (x2 - corner_length, y1), color, thickness + 1)
    cv2.line(img, (x2, y1), (x2, y1 + corner_length), color, thickness + 1)
    
    # 左下角
    cv2.line(img, (x1, y2), (x1 + corner_length, y2), color, thickness + 1)
    cv2.line(img, (x1, y2), (x1, y2 - corner_length), color, thickness + 1)
    
    # 右下角
    cv2.line(img, (x2, y2), (x2 - corner_length, y2), color, thickness + 1)
    cv2.line(img, (x2, y2), (x2, y2 - corner_length), color, thickness + 1)
    
    return img

def calculate_iou(box1, box2):
    """
    计算两个边界框的IoU(交并比)
    
    参数:
        box1: [x1, y1, x2, y2] 格式的第一个边界框
        box2: [x1, y1, x2, y2] 格式的第二个边界框
        
    返回:
        iou: 交并比值
    """
    # 确保box1和box2是正确的格式
    if len(box1) != 4 or len(box2) != 4:
        return 0.0
    
    # 计算交集区域
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    
    # 计算交集面积
    if x2 < x1 or y2 < y1:
        return 0.0  # 没有交集
    
    intersection = (x2 - x1) * (y2 - y1)
    
    # 计算各自面积
    box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
    box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
    
    # 计算并集面积
    union = box1_area + box2_area - intersection
    
    # 计算IoU
    iou = intersection / union if union > 0 else 0.0
    
    return iou

def preprocess_license_plate(img, plate_box, padding=5):
    """
    预处理车牌图像以提高OCR识别率
    
    参数:
        img: 原始图像
        plate_box: 车牌边界框 [x1, y1, x2, y2]
        padding: 边界框扩展填充像素
        
    返回:
        预处理后的车牌图像变体字典, 包含原始、二值化、增强等多种处理方式
    """
    # 提取车牌区域
    x1, y1, x2, y2 = plate_box
    # 添加填充，但确保不超出图像边界
    h, w = img.shape[:2]
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(w, x2 + padding)
    y2 = min(h, y2 + padding)
    
    plate_img = img[y1:y2, x1:x2]
    if plate_img.size == 0:
        return None
    
    # 调整大小，保持宽高比
    target_height = 48
    ratio = target_height / plate_img.shape[0]
    target_width = int(plate_img.shape[1] * ratio)
    plate_img = cv2.resize(plate_img, (target_width, target_height))
    
    # 保存原始图像
    original = plate_img.copy()
    
    # 1. 转换为灰度图
    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
    
    # 2. 高斯模糊去除噪点
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    
    # 3. 自适应直方图均衡化(CLAHE)增强对比度
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(blur)
    
    # 4. 锐化处理增强边缘
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    sharpened = cv2.filter2D(enhanced, -1, kernel)
    
    # 5. 自适应阈值二值化
    binary_adaptive = cv2.adaptiveThreshold(
        sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY_INV, 11, 2
    )
    
    # 6. 形态学操作去除噪点和连接断开的字符
    kernel = np.ones((2, 2), np.uint8)
    morph = cv2.morphologyEx(binary_adaptive, cv2.MORPH_CLOSE, kernel)
    morph = cv2.morphologyEx(morph, cv2.MORPH_OPEN, kernel)
    
    # 7. 反转为正常的黑底白字
    binary = cv2.bitwise_not(morph)
    
    # 8. 再次锐化边缘
    binary = cv2.filter2D(binary, -1, kernel)
    
    # 转回3通道图像以便于显示和保存结果
    binary_rgb = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
    
    # 9. 创建更多处理变体，返回最佳结果
    # 也返回原始彩色图和增强彩色图，便于OCR选择最佳结果
    color_enhanced = cv2.convertScaleAbs(plate_img, alpha=1.2, beta=10)  # 增强对比度
    
    # 10. 基于HSV创建不同的处理变体
    hsv = cv2.cvtColor(plate_img, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    
    # 增强亮度通道
    v = cv2.equalizeHist(v)
    enhanced_hsv = cv2.merge([h, s, v])
    hsv_enhanced = cv2.cvtColor(enhanced_hsv, cv2.COLOR_HSV2BGR)
    
    # 11. Sobel边缘增强
    sobel_x = cv2.Sobel(gray, cv2.CV_8U, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_8U, 0, 1, ksize=3)
    sobel = cv2.addWeighted(sobel_x, 0.5, sobel_y, 0.5, 0)
    sobel_rgb = cv2.cvtColor(sobel, cv2.COLOR_GRAY2BGR)
    
    # 12. 大津法全局二值化
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    otsu_rgb = cv2.cvtColor(otsu, cv2.COLOR_GRAY2BGR)
    
    # 13. 增加边缘锐化版本
    sharpen_kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharpen = cv2.filter2D(color_enhanced, -1, sharpen_kernel)
    
    # 创建结果字典，包含所有变体
    results = {
        'original': original,
        'binary': binary_rgb,
        'enhanced': color_enhanced,
        'hsv_enhanced': hsv_enhanced,
        'sobel': sobel_rgb,
        'otsu': otsu_rgb,
        'sharpen': sharpen
    }
    
    return results

def format_license_plate(text):
    """
    格式化识别出的车牌文本
    
    参数:
        text: 原始OCR识别文本
        
    返回:
        格式化后的车牌
    """
    if not text:
        return ""
    
    # 去除空白字符
    text = text.strip()
    
    # 中国车牌常见格式: 例如"粤B12345"
    # 去除非字母数字字符，但保留 · 字符（新能源车牌使用）
    cleaned_text = ''.join(c for c in text if c.isalnum() or c == '·')
    
    # 中国车牌有7-8个字符
    if len(cleaned_text) < 6 or len(cleaned_text) > 9:
        # 尝试识别特殊情况
        if len(cleaned_text) > 9:
            # 可能是多个车牌重叠，尝试提取前8个字符
            cleaned_text = cleaned_text[:8]
        elif len(cleaned_text) < 6:
            # 太短的文本可能识别不完整，保留原始内容
            return text
    
    # 中国省份简称列表
    provinces = ['京', '津', '沪', '渝', '冀', '豫', '云', '辽', '黑', 
                '湘', '皖', '鲁', '新', '苏', '浙', '赣', '鄂', '桂', 
                '甘', '晋', '蒙', '陕', '吉', '闽', '贵', '粤', '青', 
                '藏', '川', '宁', '琼']
    
    # 修正常见OCR错误
    error_mapping = {
        '0': 'D', '1': 'I', 'l': 'I', 'o': 'O', 'q': 'Q',
        '2': 'Z', '5': 'S', '8': 'B', 
        'nn': 'M', 'rn': 'M', 'rrn': 'M'
    }
    
    for error, correction in error_mapping.items():
        cleaned_text = cleaned_text.replace(error, correction)
    
    # 如果识别到的车牌中没有省份简称，检查第一个字符
    if not any(p in cleaned_text[:1] for p in provinces):
        # 无法确定省份简称，但长度合适，可能是无法识别的省份字符
        # 尝试保持格式，假设第一个字符是省份简称
        if len(cleaned_text) >= 7:
            province = cleaned_text[0]
            city = cleaned_text[1]
            number = cleaned_text[2:]
            
            # 格式化为标准车牌格式
            formatted = f"{province}{city}·{number}"
            return formatted
    else:
        # 提取车牌中的省份、城市和编号部分
        if len(cleaned_text) >= 7:
            province = cleaned_text[0]
            city = cleaned_text[1]
            number = cleaned_text[2:]
            
            # 如果车牌第二位应该是字母而识别为数字，尝试纠正
            if city.isdigit():
                potential_letters = {'0': 'O', '1': 'I', '2': 'Z', '3': 'B', '5': 'S', '8': 'B'}
                if city in potential_letters:
                    city = potential_letters[city]
            
            # 格式化为标准车牌格式
            if len(cleaned_text) == 7:  # 普通车牌
                formatted = f"{province}{city}{number}"
                return formatted
            elif len(cleaned_text) == 8:  # 新能源车牌
                formatted = f"{province}{city}·{number}"
                return formatted
    
    # 如果上述逻辑没有格式化成功，返回清理后的文本
    return cleaned_text

def load_classes(classes_file):
    """
    从类别文件中加载类别名称
    
    参数:
        classes_file: 类别文件路径
        
    返回:
        dict: 类别ID到类名的映射
    """
    classes = {}
    try:
        with open(classes_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    parts = line.split(' ', 1)
                    if len(parts) == 2:
                        class_id = int(parts[0])
                        class_name = parts[1].strip()
                        classes[class_id] = class_name
        print(f"已从{classes_file}加载{len(classes)}个类别")
    except Exception as e:
        print(f"加载类别文件出错: {e}")
        # 使用默认类别
        classes = {
            0: "car",
            1: "bus",
            2: "tanker",
            3: "container_truck",
            4: "truck",
            5: "van",
            6: "pickup",
            7: "special_vehicle",
            8: "license_plate",
            9: "accident"
        }
        print("使用默认类别映射")
    
    return classes

def draw_boxes(image, boxes, labels, confidences, thickness=2):
    """
    在图像上绘制检测框
    
    参数:
        image: 输入图像
        boxes: 检测框列表 [[x1, y1, x2, y2], ...]
        labels: 标签列表
        confidences: 置信度列表
        thickness: 线条粗细
        
    返回:
        绘制了检测框的图像
    """
    img_copy = image.copy()
    for box, label, conf in zip(boxes, labels, confidences):
        x1, y1, x2, y2 = [int(v) for v in box]
        color = (0, 255, 0)  # 默认绿色
        
        # 根据类别名称调整颜色
        if 'license' in label.lower():
            color = (255, 0, 0)  # 车牌用蓝色
        elif 'accident' in label.lower():
            color = (0, 0, 255)  # 事故用红色
        
        # 绘制边界框
        cv2.rectangle(img_copy, (x1, y1), (x2, y2), color, thickness)
        
        # 构建标签文本
        label_text = f"{label} {conf:.2f}"
        
        # 绘制标签背景
        text_size = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
        cv2.rectangle(img_copy, (x1, y1 - 20), (x1 + text_size[0], y1), color, -1)
        
        # 绘制标签文本
        cv2.putText(img_copy, label_text, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    return img_copy

def apply_nms(boxes, scores, iou_threshold=0.5):
    """
    应用非极大值抑制(NMS)
    
    参数:
        boxes: 边界框列表 [[x1, y1, x2, y2], ...]
        scores: 置信度列表
        iou_threshold: IoU阈值，高于此值的重叠框会被抑制
        
    返回:
        保留的框的索引列表
    """
    # 转换为numpy数组
    boxes = np.array(boxes)
    scores = np.array(scores)
    
    # 获取框的坐标
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    
    # 计算框面积
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    
    # 按置信度降序排序
    order = scores.argsort()[::-1]
    
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        
        # 计算最高置信度框与其余框的IoU
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        
        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        
        # 保留IoU小于阈值的框
        inds = np.where(ovr <= iou_threshold)[0]
        order = order[inds + 1]
    
    return keep 