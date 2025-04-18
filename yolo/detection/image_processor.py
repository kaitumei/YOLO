import cv2
import numpy as np
import os
import time
from datetime import datetime
import torch
import hashlib
import pickle
from PIL import Image
from concurrent.futures import ThreadPoolExecutor

def process_image(img_path, output_path=None, detector=None, debug=False, 
                 detect_vehicles=True, detect_plates=True, 
                 detect_accidents=False, detect_violations=False,
                 auto_open_result=False, conf_threshold=0.4):
    """
    处理单张图像，检测车辆、车牌、事故和违规
    
    参数:
        img_path: 输入图像路径
        output_path: 输出图像路径，为None时自动生成
        detector: 检测器实例
        debug: 是否启用调试模式
        detect_vehicles: 是否检测车辆
        detect_plates: 是否检测车牌
        detect_accidents: 是否检测事故
        detect_violations: 是否检测违章行为
        auto_open_result: 处理完成后是否自动打开结果
        conf_threshold: 检测置信度阈值
        
    返回:
        output_path: 处理后的图像路径
        detections: 检测结果
    """
    # 检查输入文件是否存在
    if not os.path.exists(img_path):
        raise FileNotFoundError(f"找不到输入文件: {img_path}")
    
    # 如果未指定输出路径，自动生成
    if output_path is None:
        base_name = os.path.basename(img_path)
        name, ext = os.path.splitext(base_name)
        output_path = os.path.join(os.path.dirname(img_path), f"{name}_result{ext}")
    
    # 创建输出目录
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    # 记录处理开始时间
    start_time = time.time()
    
    # 加载图像
    from .utils import draw_text_pil
    img = cv2.imread(img_path)
    if img is None:
        raise ValueError(f"无法读取图像: {img_path}")
    
    # 检查图像大小，如果太大则缩小以加快处理速度
    max_size = 1920  # 最大尺寸
    h, w = img.shape[:2]
    original_size = (w, h)
    
    if max(h, w) > max_size:
        scale = max_size / max(h, w)
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = cv2.resize(img, (new_w, new_h))
        if debug:
            print(f"图像已调整大小为 {new_w}x{new_h}")
    
    # 确保检测器可用
    if detector is None:
        raise ValueError("必须提供有效的检测器实例")
    
    # 创建结果图像
    result_img = img.copy()
    all_detections = []
    
    # 执行检测
    try:
        result_img, detections = detector.detect_objects(
            img, 
            conf_threshold=conf_threshold,
            detect_vehicles=detect_vehicles,
            detect_plates=detect_plates,
            detect_accidents=detect_accidents,
            detect_violations=detect_violations
        )
        all_detections.extend(detections)
        
        if debug:
            print(f"检测到 {len(detections)} 个对象")
    except Exception as e:
        print(f"检测失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 添加处理时间标注
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        h, w = result_img.shape[:2]
        result_img = draw_text_pil(
            result_img, 
            f"处理时间: {timestamp}", 
            (10, h-40),
            font_size=20,
            text_color=(255, 255, 255),
            bg_color=(0, 0, 0, 150),
            with_background=False
        )
        
        # 添加检测结果统计
        detection_summary = f"检测结果: {len(all_detections)} 项"
        result_img = draw_text_pil(
            result_img, 
            detection_summary, 
            (10, h-80),
            font_size=20,
            text_color=(255, 255, 255),
            bg_color=(0, 0, 0, 150),
            with_background=False
        )
        
        # 添加处理耗时
        elapsed_time = time.time() - start_time
        result_img = draw_text_pil(
            result_img, 
            f"处理耗时: {elapsed_time:.2f}秒", 
            (10, h-120),
            font_size=20,
            text_color=(255, 255, 255),
            bg_color=(0, 0, 0, 150),
            with_background=False
        )
    except Exception as e:
        print(f"添加时间戳失败: {e}")
    
    # 如果调整过大小，恢复到原始大小
    if original_size != (w, h):
        result_img = cv2.resize(result_img, original_size)
    
    # 保存结果图像
    try:
        cv2.imwrite(output_path, result_img)
        if debug:
            print(f"结果已保存到: {output_path}")
    except Exception as e:
        print(f"保存结果失败: {e}")
        # 尝试使用PIL保存
        try:
            result_pil = Image.fromarray(cv2.cvtColor(result_img, cv2.COLOR_BGR2RGB))
            result_pil.save(output_path)
            if debug:
                print(f"使用PIL成功保存结果到: {output_path}")
        except Exception as pil_e:
            print(f"使用PIL保存也失败: {pil_e}")
            raise
    
    # 如果需要，自动打开结果
    if auto_open_result and os.path.exists(output_path):
        try:
            import platform
            import subprocess
            
            if platform.system() == 'Darwin':  # macOS
                subprocess.call(['open', output_path])
            elif platform.system() == 'Windows':  # Windows
                os.startfile(output_path)
            else:  # Linux
                subprocess.call(['xdg-open', output_path])
        except Exception as e:
            print(f"无法自动打开结果图像: {e}")
    
    return output_path, all_detections

def process_images_batch(image_paths, output_dir, detector, 
                        detect_vehicles=True, detect_plates=True, 
                        detect_accidents=False, detect_violations=False, 
                        conf_threshold=0.4, debug=False, num_workers=4):
    """
    批量处理多张图像
    
    参数:
        image_paths: 图像路径列表
        output_dir: 输出目录
        detector: 检测器实例
        detect_vehicles: 是否检测车辆
        detect_plates: 是否检测车牌
        detect_accidents: 是否检测事故
        detect_violations: 是否检测违章行为
        conf_threshold: 检测置信度阈值
        debug: 是否启用调试模式
        num_workers: 工作线程数
        
    返回:
        results: 处理结果列表 [(输出路径, 检测结果)]
    """
    # 确保输出目录存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    # 记录开始时间
    start_time = time.time()
    
    # 定义单张图像处理函数
    def process_single_image(img_path):
        try:
            # 生成输出路径
            base_name = os.path.basename(img_path)
            name, ext = os.path.splitext(base_name)
            output_path = os.path.join(output_dir, f"{name}_result{ext}")
            
            # 调用图像处理函数
            result_path, detections = process_image(
                img_path, 
                output_path=output_path,
                detector=detector,
                debug=False,  # 批处理时不显示调试信息
                detect_vehicles=detect_vehicles,
                detect_plates=detect_plates,
                detect_accidents=detect_accidents,
                detect_violations=detect_violations,
                auto_open_result=False,
                conf_threshold=conf_threshold
            )
            
            return (result_path, detections, None)
        except Exception as e:
            if debug:
                print(f"处理图像失败 {img_path}: {e}")
            return (None, [], str(e))
    
    # 使用线程池并行处理图像
    results = []
    failed_count = 0
    success_count = 0
    
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        # 提交所有任务
        futures = [executor.submit(process_single_image, path) for path in image_paths]
        
        # 添加进度指示器
        total = len(image_paths)
        
        if debug:
            print(f"开始批量处理 {total} 张图像...")
        
        # 处理结果
        for i, future in enumerate(futures):
            try:
                output_path, detections, error = future.result()
                
                if output_path is not None:
                    results.append((output_path, detections))
                    success_count += 1
                else:
                    failed_count += 1
                
                if debug:
                    print(f"进度: {i+1}/{total} [{success_count}成功/{failed_count}失败]", end='\r')
            except Exception as e:
                if debug:
                    print(f"任务执行失败: {e}")
                failed_count += 1
    
    # 计算总处理时间
    elapsed_time = time.time() - start_time
    
    if debug:
        print(f"\n批量处理完成: {success_count}成功, {failed_count}失败, 耗时: {elapsed_time:.2f}秒")
    
    return results 