"""
车辆分析模块

此模块提供车辆特征分析功能，如颜色识别。
"""

import cv2
import numpy as np

def identify_vehicle_color(vehicle_region):
    """
    识别车辆的主要颜色
    
    参数:
        vehicle_region: 车辆图像区域
    
    返回:
        color_name: 颜色名称
        rgb_color: RGB颜色值
    """
    # 确保有效的车辆区域
    if vehicle_region is None or vehicle_region.size == 0:
        return "未知", (100, 100, 100)
        
    try:
        # 缩小图像以加快处理速度
        height, width = vehicle_region.shape[:2]
        if width > 100:
            scale = 100 / width
            resized = cv2.resize(vehicle_region, (100, int(height * scale)))
        else:
            resized = vehicle_region
        
        # 转换为RGB色彩空间
        rgb_img = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        
        # 创建掩码排除背景
        hsv_img = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
        lower_bound = np.array([0, 30, 30])
        upper_bound = np.array([180, 255, 255])
        mask = cv2.inRange(hsv_img, lower_bound, upper_bound)
        
        # 提取有效像素
        valid_pixels = rgb_img[mask > 0]
        
        # 如果没有有效像素，返回未知
        if len(valid_pixels) == 0:
            return "未知", (100, 100, 100)
        
        # 使用K均值聚类找到主要颜色
        pixels = valid_pixels.reshape(-1, 3).astype(np.float32)
        
        # 根据有效像素数量动态调整k值
        # 确保k值不大于有效像素点数量
        k = min(3, len(pixels))
        
        # 如果像素数量太少，直接计算平均颜色
        if k <= 1 or len(pixels) < 3:
            # 当像素太少时，直接计算平均颜色而不使用聚类
            dominant_color = np.mean(pixels, axis=0)
            rgb_color = tuple(map(int, dominant_color))
        else:
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
            _, labels, centers = cv2.kmeans(pixels, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
            
            # 计算每个簇的像素数量
            counts = np.bincount(labels.flatten())
            
            # 获取最大簇的颜色中心
            dominant_color = centers[np.argmax(counts)]
            rgb_color = tuple(map(int, dominant_color))
        
        # 定义基本颜色范围
        color_ranges = {
            "黑色": ([0, 0, 0], [50, 50, 50]),
            "白色": ([200, 200, 200], [255, 255, 255]),
            "灰色": ([70, 70, 70], [140, 140, 140]),
            "红色": ([150, 0, 0], [255, 50, 50]),
            "蓝色": ([0, 0, 150], [50, 50, 255]),
            "绿色": ([0, 150, 0], [50, 255, 50]),
            "黄色": ([200, 200, 0], [255, 255, 50]),
            "银色": ([180, 180, 180], [210, 210, 210]),
        }
        
        # 确定颜色名称
        color_name = "未知"
        for name, (lower, upper) in color_ranges.items():
            lower = np.array(lower)
            upper = np.array(upper)
            if np.all(dominant_color >= lower) and np.all(dominant_color <= upper):
                color_name = name
                break
        
        return color_name, rgb_color
        
    except Exception as e:
        # 捕获所有异常，确保函数不会崩溃
        import traceback
        print(f"车辆颜色识别失败: {e}")
        traceback.print_exc()
        return "未知", (100, 100, 100) 