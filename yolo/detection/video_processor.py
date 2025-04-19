import cv2
import os
import time
from datetime import datetime, timedelta
import numpy as np
import concurrent.futures
from tqdm import tqdm
import signal
import torch
import logging
import platform
import threading

# 配置日志
logger = logging.getLogger("video_processor")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    # 创建格式器
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    # 添加处理器到日志器
    logger.addHandler(console_handler)

# 修改绝对导入为相对导入
from .vehicle_analyzer import identify_vehicle_color
from .license_plate_ocr import LicensePlateOCR
from .class_mapper import get_vehicle_class_name
from .utils import draw_fancy_box, draw_text_pil

# 检查操作系统类型
is_windows = platform.system() == 'Windows'

# 超时异常类
class TimeoutError(Exception):
    pass

# 定义Windows平台的超时装饰器
def timeout_handler(timeout):
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = [None]
            error = [None]
            
            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    error[0] = e
            
            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(timeout)
            
            if thread.is_alive():
                raise TimeoutError(f"操作超时 ({timeout}秒)")
            
            if error[0]:
                raise error[0]
                
            return result[0]
        return wrapper
    return decorator

# 定义一个draw_fancy_text函数作为替代
def draw_fancy_text(img, text, position, font_size=24, text_color=(255, 255, 255), 
                   bg_color=None, add_shadow=True):
    """
    在图像上绘制美观的文本
    
    参数:
        img: 输入图像
        text: 要绘制的文本
        position: 文本位置 (x, y)
        font_size: 字体大小
        text_color: 文本颜色
        bg_color: 背景颜色，None表示无背景
        add_shadow: 是否添加阴影
        
    返回:
        添加文本后的图像
    """
    x, y = position
    
    # 绘制文本阴影（如果需要）
    if add_shadow:
        shadow_img = img.copy()
        shadow_img = draw_text_pil(
            shadow_img, 
            text, 
            (x+2, y+2), 
            font_size=font_size,
            text_color=(0, 0, 0),  # 黑色阴影
            with_background=False
        )
        # 使用阴影图像作为基础
        img = shadow_img
    
    # 绘制主文本
    result = draw_text_pil(
        img, 
        text, 
        position, 
        font_size=font_size,
        text_color=text_color,
        bg_color=bg_color if bg_color is not None else (0, 0, 0, 180),
        with_background=bg_color is not None
    )
    
    return result

# 定义一个recognize_plate函数作为备用
def recognize_plate(plate_img, ocr_model=None):
    """
    识别车牌文字及颜色
    
    参数:
        plate_img: 车牌图像
        ocr_model: OCR模型实例
        
    返回:
        plate_text: 车牌文本
        confidence: 置信度
        plate_color: 车牌颜色
        bg_color: 背景颜色
    """
    plate_text = "未识别"
    confidence = 0.0
    plate_color = "未知"
    bg_color = (0, 0, 255)  # 默认蓝色背景
    
    try:
        if ocr_model is not None:
            # 尝试使用OCR模型识别
            result = ocr_model.recognize(plate_img)
            if result and 'text' in result:
                plate_text = result['text']
                confidence = result.get('confidence', 0.5)
                plate_color = result.get('color', "蓝色")
                
                # 根据车牌颜色设置背景颜色
                if '蓝' in plate_color:
                    bg_color = (255, 0, 0)  # 蓝色(BGR)
                elif '黄' in plate_color:
                    bg_color = (0, 255, 255)  # 黄色
                elif '绿' in plate_color:
                    bg_color = (0, 255, 0)  # 绿色
                elif '白' in plate_color:
                    bg_color = (255, 255, 255)  # 白色
                elif '黑' in plate_color:
                    bg_color = (0, 0, 0)  # 黑色
    except Exception as e:
        logger.warning(f"车牌识别失败: {e}")
    
    return plate_text, confidence, plate_color, bg_color

# 视频处理函数
def process_video(video_path, output_path=None, detector=None, 
                 enable_license_plate=True, enable_speed=False,
                 show_preview=False, skip_frames=2, 
                 timestamp_format='%Y-%m-%d %H:%M:%S',
                 start_time=None, fps_override=None, batch_size=4,
                 timeout=600):
    """
    处理视频文件并应用检测
    
    参数:
        video_path: 视频文件路径
        output_path: 输出文件路径 (如果为None，则自动生成)
        detector: 检测器实例 (如果为None，则使用默认检测器)
        enable_license_plate: 是否启用车牌检测
        enable_speed: 是否启用速度检测 
        show_preview: 是否显示预览
        skip_frames: 跳过的帧数
        timestamp_format: 时间戳格式
        start_time: 视频开始时间 (如果为None，则使用当前时间)
        fps_override: 覆盖视频帧率
        batch_size: 批处理大小
        timeout: 超时时间(秒)
        
    返回:
        tuple: (输出路径, 处理结果列表)
    """
    # 存储处理结果的列表
    processing_results = []
    
    # 处理超时的变量
    timeout_occurred = False
    timer = None
    cap = None
    out = None
    
    try:
        # 验证视频路径
        if not os.path.exists(video_path):
            logger.error(f"错误: 视频文件不存在 {video_path}")
            return None, processing_results
            
        # 设置超时处理
        def handle_timeout():
            nonlocal timeout_occurred
            timeout_occurred = True
            logger.error(f"视频处理超时 ({timeout}秒)")
            
        # 设置跨平台的超时机制
        if timeout > 0:
            if not is_windows:
                # Linux/Unix系统使用信号
                try:
                    signal.signal(signal.SIGALRM, lambda signum, frame: handle_timeout())
                    signal.alarm(timeout)
                except AttributeError:
                    # 如果SIGALRM不可用，使用线程
                    timer = threading.Timer(timeout, handle_timeout)
                    timer.daemon = True
                    timer.start()
            else:
                # Windows系统使用线程
                timer = threading.Timer(timeout, handle_timeout)
                timer.daemon = True
                timer.start()
        
        # 生成输出路径(如果未提供)
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.splitext(os.path.basename(video_path))[0]
            output_path = f"output/{filename}_processed_{timestamp}.mp4"
            
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # 打开视频文件
        retry_count = 0
        max_retries = 3
        
        logger.info(f"开始处理视频: {video_path}")
        
        while retry_count < max_retries:
            try:
                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    logger.warning(f"尝试 {retry_count+1}/{max_retries}: 无法打开视频文件 {video_path}")
                    retry_count += 1
                    time.sleep(1)  # 等待一秒再重试
                    continue
                break  # 成功打开，跳出循环
            except Exception as e:
                logger.error(f"尝试 {retry_count+1}/{max_retries} 打开视频失败: {str(e)}")
                retry_count += 1
                time.sleep(1)
                if retry_count >= max_retries:
                    logger.error(f"无法打开视频文件 {video_path}，已达到最大重试次数")
                    return None, processing_results
        
        # 获取视频属性
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # 验证FPS值
        if fps <= 0 or fps > 120:
            logger.warning(f"警告: 检测到异常帧率 {fps}，使用默认值 25")
            fps = 25
            
        # 允许覆盖FPS
        if fps_override and fps_override > 0:
            fps = fps_override
            logger.info(f"帧率已覆盖为: {fps}")
            
        # 验证总帧数
        if total_frames <= 0:
            logger.warning("警告: 无法获取总帧数，将尝试处理至视频结束")
            total_frames = float('inf')
            
        logger.info(f"视频信息: {width}x{height}, {fps:.2f}fps, 总帧数: {total_frames}")
        
        # 创建输出视频
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # 使用MP4编码
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        # 检查输出视频是否已创建
        if not out.isOpened():
            logger.error(f"无法创建输出视频文件: {output_path}")
            cap.release()
            return None, processing_results
            
        # 初始化帧计数
        frame_count = 0
        processed_count = 0
        
        # 初始化处理开始时间
        processing_start = time.time()
        
        # 初始化进度条
        pbar = tqdm(total=total_frames, desc="处理视频", unit="帧")
        
        # 设置视频开始时间
        if start_time is None:
            start_time = datetime.now()
        
        # 初始化跟踪器
        vehicle_trackers = []
        plate_trackers = []
        
        # 初始化帧缓冲区用于批处理
        frames_buffer = []
        frame_indices = []
        
        # 处理视频帧
        while cap.isOpened() and not timeout_occurred:
            ret, frame = cap.read()
            if not ret:
                break
                
            frame_count += 1
            pbar.update(1)
            
            # 跳过帧以加快处理
            if skip_frames > 0 and frame_count % skip_frames != 0:
                continue
                
            processed_count += 1
            
            # 将帧添加到缓冲区
            frames_buffer.append(frame)
            frame_indices.append(frame_count)
            
            # 当缓冲区达到批处理大小或者是最后一帧时，进行处理
            if len(frames_buffer) >= batch_size or frame_count == total_frames:
                try:
                    # 批量处理帧
                    if detector is not None:
                        # 用于存储批处理后的结果
                        vehicle_boxes = []
                        plate_detections = []
                        
                        for i, (buf_frame, idx) in enumerate(zip(frames_buffer, frame_indices)):
                            current_time = start_time + timedelta(seconds=idx/fps)
                            timestamp = current_time.strftime(timestamp_format)
                            
                            # 检测物体
                            detection_result = detector.detect_objects(
                                buf_frame, 
                                detect_vehicles=True,
                                detect_plates=enable_license_plate,
                                detect_accidents=False,
                                detect_violations=False
                            )
                            
                            # 检查返回值格式，确保结果正确解析
                            if isinstance(detection_result, tuple) and len(detection_result) >= 2:
                                # 正常情况：(result_image, detections)
                                annotated_frame, detections = detection_result
                                
                                # 使用已标注的图像替换原始帧
                                frames_buffer[i] = annotated_frame
                                
                                # 处理结果数据
                                frame_result = {
                                    'frame': idx,
                                    'timestamp': timestamp,
                                    'vehicles': [],
                                    'license_plates': []
                                }
                                
                                # 从detections中提取车辆和车牌信息
                                for detection in detections:
                                    if not isinstance(detection, dict):
                                        continue
                                        
                                    # 获取基本信息
                                    box = detection.get('coordinates', [0, 0, 0, 0])
                                    x1, y1, x2, y2 = box
                                    cls_id = detection.get('class_id', -1)
                                    class_name = detection.get('class_name', '未知')
                                    conf = detection.get('confidence', 0.0)
                                    
                                    # 处理车辆检测
                                    if cls_id < 8:  # 车辆类别
                                        vehicle_color = detection.get('vehicle_color', '未知')
                                        
                                        # 添加到处理结果
                                        frame_result['vehicles'].append({
                                            'type': class_name,
                                            'class': class_name,  # 添加class字段以兼容前端
                                            'class_name': class_name,  # 添加class_name字段以兼容前端
                                            'box': box,
                                            'conf': float(conf),
                                            'color': vehicle_color,
                                            'rgb': (0, 0, 255)  # 默认红色 (BGR)
                                        })
                                        
                                        # 添加到跟踪器
                                        vehicle_boxes.append({
                                            'box': box,
                                            'type': class_name,
                                            'class': class_name,  # 添加class字段以兼容前端
                                            'class_name': class_name,  # 添加class_name字段以兼容前端
                                            'conf': float(conf),
                                            'color': vehicle_color,
                                            'rgb': (0, 0, 255)  # 默认红色 (BGR)
                                        })
                                    
                                    # 处理车牌检测
                                    elif cls_id == 8 and enable_license_plate:  # 车牌类别
                                        plate_text = detection.get('plate_text', '未识别')
                                        plate_conf = detection.get('plate_conf', 0.0)
                                        plate_color = detection.get('plate_color', '蓝色')
                                        
                                        # 根据车牌颜色设置背景颜色
                                        if '蓝' in plate_color:
                                            bg_color = (255, 0, 0)  # 蓝色(BGR)
                                        elif '黄' in plate_color:
                                            bg_color = (0, 255, 255)  # 黄色
                                        elif '绿' in plate_color:
                                            bg_color = (0, 255, 0)  # 绿色
                                        elif '白' in plate_color:
                                            bg_color = (255, 255, 255)  # 白色
                                        elif '黑' in plate_color:
                                            bg_color = (0, 0, 0)  # 黑色
                                        else:
                                            bg_color = (0, 0, 255)  # 默认红色
                                        
                                        # 添加到处理结果
                                        frame_result['license_plates'].append({
                                            'text': plate_text,
                                            'class': '车牌',  # 添加class字段以兼容前端
                                            'class_name': '车牌',  # 添加class_name字段以兼容前端
                                            'box': box,
                                            'conf': float(plate_conf or conf),
                                            'color': plate_color
                                        })
                                        
                                        # 添加到跟踪器
                                        plate_detections.append({
                                            'box': box,
                                            'text': plate_text,
                                            'class': '车牌',  # 添加class字段以兼容前端
                                            'class_name': '车牌',  # 添加class_name字段以兼容前端
                                            'conf': float(plate_conf or conf),
                                            'color': plate_color,
                                            'bg_color': bg_color
                                        })
                                
                                # 添加到处理结果列表
                                processing_results.append(frame_result)
                            else:
                                # 处理异常情况
                                logger.warning(f"检测结果格式不正确: {type(detection_result)}")
                                
                                # 添加空结果
                                processing_results.append({
                                    'frame': idx,
                                    'timestamp': timestamp,
                                    'vehicles': [],
                                    'license_plates': []
                                })
                    
                    # 更新跟踪器
                    if frames_buffer:
                        # 使用最后一帧的检测结果更新跟踪器已经不需要，因为我们直接使用标注后的图像
                        pass
                    
                    # 写入所有标注后的帧到输出视频
                    for i, buf_frame in enumerate(frames_buffer):
                        # 显示预览
                        if show_preview:
                            try:
                                cv2.imshow('Video Processing', buf_frame)
                                if cv2.waitKey(1) & 0xFF == ord('q'):  # 按q退出
                                    break
                            except Exception as preview_error:
                                logger.error(f"显示预览出错: {preview_error}")
                                show_preview = False  # 关闭预览功能
                        
                        # 写入输出视频
                        out.write(buf_frame)
                
                except torch.cuda.OutOfMemoryError:
                    logger.warning("警告: CUDA内存不足，尝试清理缓存")
                    torch.cuda.empty_cache()
                    # 尝试减小批处理大小
                    if batch_size > 1:
                        batch_size = max(1, batch_size // 2)
                        logger.warning(f"减小批处理大小至 {batch_size}")
                    # 写入未处理的帧
                    for buf_frame in frames_buffer:
                        out.write(buf_frame)
                except Exception as e:
                    logger.error(f"处理帧 {frame_indices} 出错: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    # 写入未处理的帧
                    for buf_frame in frames_buffer:
                        out.write(buf_frame)
                finally:
                    # 清空缓冲区
                    frames_buffer = []
                    frame_indices = []
        
        # 关闭进度条
        pbar.close()
        
        elapsed_time = time.time() - processing_start
        fps_rate = processed_count / elapsed_time if elapsed_time > 0 else 0
        
        logger.info(f"视频处理完成! 已保存到: {output_path}")
        logger.info(f"总处理时间: {elapsed_time:.2f}秒, 处理了 {processed_count} 帧, 处理速率: {fps_rate:.2f} 帧/秒")
        
        # 检查输出文件
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"输出视频文件大小: {os.path.getsize(output_path)/1024/1024:.2f} MB")
        else:
            logger.warning(f"警告: 输出视频可能有问题，请检查 {output_path}")
        
        return output_path, processing_results
        
    except KeyboardInterrupt:
        logger.info("处理被用户中断")
        return output_path if 'output_path' in locals() else None, processing_results
    except Exception as e:
        logger.error(f"视频处理出错: {e}")
        import traceback
        traceback.print_exc()
        return output_path if 'output_path' in locals() else None, processing_results
    finally:
        # 取消超时定时器
        if timer:
            timer.cancel()
            
        # 取消信号警报(如果在非Windows系统设置了)
        if not is_windows:
            try:
                signal.alarm(0)
            except:
                pass
            
        # 释放资源
        try:
            if cap:
                cap.release()
        except:
            pass
            
        try:
            if out:
                out.release()
        except:
            pass
            
        try:
            cv2.destroyAllWindows()
        except:
            pass
    
    return output_path, processing_results

# 原始视频处理函数，保持不变
def process_video_original(video_path, model, rec_model, output_path=None, detect_collisions=False,
                 recognize_plates=True, show_preview=False, enhance_video=False,
                 skip_frames=1, use_gpu=False, timestamp_format='%Y-%m-%d %H:%M:%S',
                 start_time=None, fps_override=None, license_model=None, plate_ocr=None,
                 only_license_plate=False):
    """
    处理视频中的车牌识别
    
    参数:
        video_path: 视频文件路径
        model: YOLO模型
        rec_model: 车牌识别模型
        output_path: 输出视频路径，默认为原视频名称加上_processed后缀
        recognize_plates: 是否识别车牌号码
        show_preview: 是否显示处理预览
        enhance_videos: 是否进行图像增强
        use_gpu: 是否使用GPU加速
        license_model: 专用车牌检测模型
    """
    logger.info(f"\n处理视频: {video_path}")
    logger.info(f"使用{'GPU' if use_gpu else 'CPU'}处理")
    
    # 验证视频文件是否存在
    if not os.path.exists(video_path):
        logger.error(f"错误: 视频文件不存在 {video_path}")
        return False
        
    # 重试打开视频文件机制
    max_attempts = 3
    attempt = 0
    cap = None
    
    while attempt < max_attempts:
        try:
            # 打开视频文件
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                break
                
            attempt += 1
            logger.warning(f"尝试打开视频失败，重试 ({attempt}/{max_attempts})...")
            time.sleep(1)
        except Exception as e:
            attempt += 1
            logger.error(f"打开视频出错: {e}, 重试 ({attempt}/{max_attempts})...")
            time.sleep(1)
    
    if not cap or not cap.isOpened():
        logger.error(f"错误: 无法打开视频 {video_path}，已尝试 {max_attempts} 次")
        return False
    
    # 获取视频信息
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # 处理无效的视频属性
    if fps <= 0:
        logger.warning("警告: 无效的FPS值，使用默认值25")
        fps = 25
    
    if total_frames <= 0:
        logger.warning("警告: 无法获取总帧数，将不显示处理进度百分比")
        total_frames = float('inf')  # 设置为无限大
    
    logger.info(f"视频信息: {width}x{height}, {fps}fps, 共{total_frames}帧")
    
    # 设置输出视频
    if output_path is None:
        base_name = os.path.basename(video_path)
        name, ext = os.path.splitext(base_name)
        output_path = os.path.join("results", f"{name}_processed{ext}")
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    # 创建视频写入器
    try:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # 使用MP4编码
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        if not out.isOpened():
            raise Exception(f"无法创建输出视频文件: {output_path}")
    except Exception as e:
        cap.release()
        logger.error(f"创建输出视频失败: {e}")
        return False
    
    # 帧计数器和跟踪变量
    frame_count = 0
    processed_count = 0
    processing_start = time.time()
    last_log_time = processing_start
    log_interval = 5  # 每5秒记录一次进度
    
    # 添加车辆跟踪
    vehicle_trackers = []  # 存储车辆跟踪信息
    plate_trackers = []    # 存储车牌跟踪信息
    last_detection_frame = 0
    detection_interval = 5  # 每隔多少帧进行一次完整检测
    
    # 添加错误处理和恢复变量
    consecutive_failures = 0
    max_failures = 10  # 允许的最大连续失败次数
    processing_timeout = 1800  # 30分钟处理超时
    
    try:
        # 逐帧处理视频
        while True:
            # 检查处理超时
            current_time = time.time()
            if current_time - processing_start > processing_timeout:
                logger.warning(f"警告: 处理时间超过 {processing_timeout/60} 分钟，提前结束")
                break
                
            # 定期记录进度
            if current_time - last_log_time > log_interval:
                elapsed = current_time - processing_start
                if total_frames != float('inf'):
                    progress = frame_count / total_frames * 100
                    remaining = (total_frames - frame_count) / (frame_count / elapsed) if frame_count > 0 else 0
                    logger.info(f"进度: {progress:.1f}%, 已处理 {frame_count} 帧, 用时: {elapsed:.1f}秒, 预计剩余: {remaining:.1f}秒")
                else:
                    logger.info(f"已处理 {frame_count} 帧, 用时: {elapsed:.1f}秒")
                last_log_time = current_time
            
            # 读取帧
            try:
                ret, frame = cap.read()
            except Exception as e:
                logger.error(f"读取帧出错: {e}")
                consecutive_failures += 1
                if consecutive_failures > max_failures:
                    logger.error(f"连续 {max_failures} 次读取失败，终止处理")
                    break
                continue
                
            if not ret:
                consecutive_failures += 1
                
                # 如果接近视频末尾，正常退出
                if total_frames != float('inf') and frame_count >= total_frames * 0.95:
                    logger.info(f"已处理视频的 {(frame_count/total_frames*100):.1f}%，视为正常完成")
                    break
                    
                if consecutive_failures > max_failures:
                    logger.error(f"连续 {max_failures} 次读取失败，终止处理")
                    break
                    
                # 短暂暂停，避免CPU高负载
                time.sleep(0.1)
                continue
            
            # 重置连续失败计数
            consecutive_failures = 0
            frame_count += 1
            
            # 只处理一部分帧以提高速度(每隔几帧处理一次)
            if frame_count % skip_frames != 0 and frame_count > 1:
                # 仍然绘制之前检测到的车辆框
                try:
                    # 绘制之前检测到的车辆
                    if vehicle_trackers:
                        for tracker in vehicle_trackers:
                            x1, y1, x2, y2 = tracker['box']
                            vehicle_type = tracker['type']
                            conf = tracker['conf']
                            color_name = tracker.get('color', 'unknown')
                            rgb_color = tracker.get('rgb', (100, 100, 100))
                            
                            # 使用识别的颜色自定义边界框颜色
                            box_color = (int(rgb_color[2]), int(rgb_color[1]), int(rgb_color[0]))
                            
                            # 绘制车辆边界框
                            frame = draw_fancy_box(
                                frame, 
                                x1, y1, x2, y2, 
                                thickness=2, 
                                box_type='normal',
                                custom_color=box_color
                            )
                            
                            # 绘制车辆标签（移除颜色显示）
                            display_text = f"{vehicle_type} {conf:.2f}"
                            
                            frame = draw_fancy_text(
                                frame,
                                display_text,
                                (x1, max(0, y1 - 30)),
                                font_size=24,
                                text_color=(255, 255, 255),
                                bg_color=None,
                                add_shadow=True
                            )
                    
                    # 绘制之前检测到的车牌
                    if recognize_plates and plate_trackers:
                        for plate in plate_trackers:
                            x1, y1, x2, y2 = plate['box']
                            plate_text = plate['text']
                            confidence = plate['conf']
                            plate_color = plate.get('color', 'unknown')
                            bg_color = plate.get('bg_color', (0, 0, 255))
                            
                            # 绘制车牌边界框
                            frame = draw_fancy_box(
                                frame, 
                                x1, y1, x2, y2, 
                                thickness=2, 
                                box_type='plate',
                                custom_color=(255, 0, 0)  # 蓝色边框
                            )
                            
                            # 计算文本位置
                            text_position = (x1, max(0, y1 - 40))  # 在车牌上方绘制文本
                            
                            # 如果文本位置在图像顶部以外，则在车牌下方绘制
                            if text_position[1] < 10:
                                text_position = (x1, y2 + 10)
                            
                            # 添加车牌文本信息
                            frame = draw_fancy_text(
                                frame,
                                f"{plate_text} [{plate_color}] {confidence:.2f}",
                                text_position,
                                font_size=24,
                                text_color=(255, 255, 255),
                                bg_color=(0, 120, 0),  # 绿色背景
                                add_shadow=True
                            )
                
                    # 写入视频
                    out.write(frame)
                except Exception as e:
                    logger.error(f"跳帧处理出错: {e}")
                
                continue
            
            processed_count += 1
            logger.info(f"处理第 {frame_count}/{total_frames} 帧...")
            
            try:
                # 车辆和车牌检测
                results = model(frame)
                
                # 提取车辆和车牌
                vehicle_boxes = []
                plate_detections = []
                
                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        try:
                            cls = int(box.cls.item())
                            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                            conf = box.conf.item()
                            
                            if conf < 0.4:  # 忽略低置信度检测，提高到0.4
                                continue
                                
                            if cls in [0, 1, 2, 3, 4, 5, 6, 7]:  # 车辆类别
                                # 提取车辆区域以识别颜色
                                vehicle_region = frame[y1:y2, x1:x2]
                                color_name, rgb_color = identify_vehicle_color(vehicle_region)
                                
                                vehicle_boxes.append({
                                    'box': (x1, y1, x2, y2),
                                    'cls': cls,
                                    'conf': conf,
                                    'type': get_vehicle_class_name(cls),
                                    'color': color_name,
                                    'rgb': rgb_color
                                })
                            
                            # 检测车牌
                            if cls == 8 and recognize_plates:  # 车牌类别
                                # 增加一点padding
                                padding = 5
                                plate_x1, plate_y1 = max(x1 - padding, 0), max(y1 - padding, 0)
                                plate_x2, plate_y2 = min(x2 + padding, frame.shape[1]), min(y2 + padding, frame.shape[0])
                                
                                # 裁剪车牌区域
                                plate_img = frame[plate_y1:plate_y2, plate_x1:plate_x2]
                                
                                # 识别车牌文字
                                plate_text, confidence, plate_color, bg_color = recognize_plate(plate_img, plate_ocr)
                                
                                if confidence > 0.4:  # 只保留置信度较高的结果
                                    plate_detections.append({
                                        'box': (plate_x1, plate_y1, plate_x2, plate_y2),
                                        'text': plate_text,
                                        'conf': confidence,
                                        'color': plate_color,
                                        'bg_color': bg_color
                                    })
                        except Exception as box_error:
                            logger.error(f"处理检测框出错: {box_error}")
                            continue
                
                # 更新跟踪器
                vehicle_trackers = vehicle_boxes
                plate_trackers = plate_detections
                
                # 绘制车辆
                for vehicle in vehicle_boxes:
                    x1, y1, x2, y2 = vehicle['box']
                    vehicle_type = vehicle['type']
                    conf = vehicle['conf']
                    color_name = vehicle['color']
                    rgb_color = vehicle['rgb']
                    
                    # 使用识别的颜色自定义边界框颜色
                    box_color = (int(rgb_color[2]), int(rgb_color[1]), int(rgb_color[0]))
                    
                    # 绘制车辆边界框
                    frame = draw_fancy_box(
                        frame, 
                        x1, y1, x2, y2, 
                        thickness=2, 
                        box_type='normal',
                        custom_color=box_color
                    )
                    
                    # 绘制车辆标签（移除颜色显示）
                    display_text = f"{vehicle_type} {conf:.2f}"
                    
                    frame = draw_fancy_text(
                        frame,
                        display_text,
                        (x1, max(0, y1 - 30)),
                        font_size=24,
                        text_color=(255, 255, 255),
                        bg_color=None,
                        add_shadow=True
                    )
                
                # 绘制车牌
                if recognize_plates:
                    for plate in plate_detections:
                        x1, y1, x2, y2 = plate['box']
                        plate_text = plate['text']
                        confidence = plate['conf']
                        plate_color = plate['color']
                        bg_color = plate['bg_color']
                        
                        # 绘制车牌边界框
                        frame = draw_fancy_box(
                            frame, 
                            x1, y1, x2, y2, 
                            thickness=2, 
                            box_type='plate',
                            custom_color=(255, 0, 0)  # 蓝色边框
                        )
                        
                        # 计算文本位置
                        text_position = (x1, max(0, y1 - 40))  # 在车牌上方绘制文本
                        
                        # 如果文本位置在图像顶部以外，则在车牌下方绘制
                        if text_position[1] < 10:
                            text_position = (x1, y2 + 10)
                        
                        # 添加车牌文本信息
                        frame = draw_fancy_text(
                            frame,
                            f"{plate_text} [{plate_color}] {confidence:.2f}",
                            text_position,
                            font_size=24,
                            text_color=(255, 255, 255),
                            bg_color=(0, 120, 0),  # 绿色背景
                            add_shadow=True
                        )
                
                # 显示预览
                if show_preview:
                    try:
                        cv2.imshow('Video Processing', frame)
                        if cv2.waitKey(1) & 0xFF == ord('q'):  # 按q退出
                            break
                    except Exception as preview_error:
                        logger.error(f"显示预览出错: {preview_error}")
                        show_preview = False  # 关闭预览功能
                
                # 写入输出视频
                out.write(frame)
            
            except torch.cuda.OutOfMemoryError:
                logger.warning("警告: CUDA内存不足，尝试清理缓存")
                torch.cuda.empty_cache()
                # 尝试写入未处理的帧以保持视频连续性
                try:
                    out.write(frame)
                except:
                    pass
                continue
            except Exception as e:
                logger.error(f"处理帧出错: {e}")
                # 尝试写入未处理的帧以保持视频连续性
                try:
                    out.write(frame)
                except:
                    pass
        
        # 计算处理统计
        elapsed_time = time.time() - processing_start
        fps_rate = processed_count / elapsed_time if elapsed_time > 0 else 0
        
        logger.info(f"视频处理完成! 已保存到: {output_path}")
        logger.info(f"总处理时间: {elapsed_time:.2f}秒, 处理了 {processed_count} 帧, 处理速率: {fps_rate:.2f} 帧/秒")
        
        # 检查输出文件
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"输出视频文件大小: {os.path.getsize(output_path)/1024/1024:.2f} MB")
        else:
            logger.warning(f"警告: 输出视频可能有问题，请检查 {output_path}")
        
        return True
        
    except KeyboardInterrupt:
        logger.info("处理被用户中断")
        return False
    except Exception as e:
        logger.error(f"视频处理出错: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 释放资源
        try:
            cap.release()
        except:
            pass
            
        try:
            out.release()
        except:
            pass
            
        try:
            cv2.destroyAllWindows()
        except:
            pass
        
        # 清理临时文件夹
        if os.path.exists("temp"):
            for file in os.listdir("temp"):
                try:
                    os.remove(os.path.join("temp", file))
                except:
                    pass
            try:
                os.rmdir("temp")
            except:
                pass
    
    return True

def enhance_image(image, method='clahe'):
    """
    增强图像质量
    
    参数:
        image: 输入图像
        method: 增强方法 ('clahe', 'hist', 'gamma')
        
    返回:
        增强后的图像
    """
    try:
        # 检查输入图像
        if image is None or image.size == 0:
            logger.warning("增强图像失败: 输入图像为空")
            return image
            
        # 转换为灰度图像进行处理
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
            
        if method == 'clahe':
            # 对比度受限的自适应直方图均衡化
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
        elif method == 'hist':
            # 普通直方图均衡化
            enhanced = cv2.equalizeHist(gray)
        elif method == 'gamma':
            # 伽马校正
            gamma = 1.5
            inv_gamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in range(256)]).astype("uint8")
            enhanced = cv2.LUT(gray, table)
        else:
            logger.warning(f"未知的增强方法: {method}，使用原始图像")
            return image
            
        # 如果原始图像是彩色的，将处理后的图像转换回彩色
        if len(image.shape) == 3:
            # 将增强后的图像用于亮度通道
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            hsv[:,:,2] = enhanced
            result = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
            return result
        else:
            return enhanced
            
    except Exception as e:
        logger.error(f"图像增强失败: {str(e)}")
        return image  # 返回原始图像

# 侦测视频中的车辆和车牌
def detect_video_objects(video_path, model, frame_interval=5, recognize_plates=True, 
                         max_frames=None, use_gpu=False, plate_ocr=None):
    """
    在视频中侦测车辆和车牌
    
    参数:
        video_path: 视频文件路径
        model: YOLO模型
        frame_interval: 帧间隔
        recognize_plates: 是否识别车牌
        max_frames: 最大处理帧数
        use_gpu: 是否使用GPU
        plate_ocr: 车牌OCR模型
        
    返回:
        vehicle_results: 车辆检测结果列表
        plate_results: 车牌检测结果列表
    """
    # 打开视频文件
    if not os.path.exists(video_path):
        logger.error(f"错误: 视频文件不存在 {video_path}")
        return [], []
        
    cap = None
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"错误: 无法打开视频 {video_path}")
            return [], []
    except Exception as e:
        logger.error(f"打开视频出错: {e}")
        return [], []
    
    # 获取视频信息
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # 处理无效参数
    if fps <= 0:
        fps = 25  # 默认帧率
        
    if total_frames <= 0:
        total_frames = float('inf')  # 未知总帧数
    
    # 限制处理帧数
    if max_frames is not None:
        total_frames = min(total_frames, max_frames)
    
    # 存储结果
    vehicle_results = []
    plate_results = []
    
    # 进度计数
    frame_count = 0
    processed_count = 0
    
    # 错误处理
    consecutive_failures = 0
    max_failures = 10
    
    # 处理超时设置
    start_time = time.time()
    timeout = 1800  # 30分钟
    
    try:
        while frame_count < total_frames:
            # 检查超时
            if time.time() - start_time > timeout:
                logger.warning(f"警告: 处理超时 ({timeout/60} 分钟)")
                break
                
            try:
                ret, frame = cap.read()
            except Exception as e:
                logger.error(f"读取帧出错: {e}")
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    logger.error(f"连续 {max_failures} 次读取失败，终止处理")
                    break
                continue
                
            if not ret:
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    logger.error(f"连续 {max_failures} 次读取失败，终止处理")
                    break
                    
                # 如果接近视频末尾，视为正常结束
                if total_frames != float('inf') and frame_count >= total_frames * 0.95:
                    logger.info(f"已处理视频的 {(frame_count/total_frames*100):.1f}%，视为正常完成")
                    break
                    
                time.sleep(0.1)  # 短暂暂停
                continue
            
            # 重置错误计数
            consecutive_failures = 0
            frame_count += 1
            
            # 只处理特定间隔的帧
            if frame_count % frame_interval != 0:
                continue
            
            processed_count += 1
            timestamp = frame_count / fps  # 当前时间戳(秒)
            
            if processed_count % 10 == 0:  # 每10帧打印一次进度
                logger.info(f"处理帧 {frame_count}, 时间戳: {timestamp:.2f}秒, 已处理: {processed_count} 帧")
            
            try:
                # 检测车辆和车牌
                results = model(frame, conf=0.4)
                
                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        try:
                            cls = int(box.cls.item())
                            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                            conf = box.conf.item()
                            
                            # 车辆类别
                            if cls in [0, 1, 2, 3, 4, 5, 6, 7]:  
                                try:
                                    # 提取车辆区域以识别颜色
                                    vehicle_region = frame[y1:y2, x1:x2]
                                    color_name, rgb_color = identify_vehicle_color(vehicle_region)
                                    
                                    # 保存车辆信息
                                    vehicle_results.append({
                                        'frame': frame_count,
                                        'timestamp': timestamp,
                                        'box': (x1, y1, x2, y2),
                                        'class': cls,
                                        'type': get_vehicle_class_name(cls),
                                        'conf': conf,
                                        'color': color_name,
                                        'rgb': rgb_color
                                    })
                                except Exception as vehicle_error:
                                    logger.warning(f"处理车辆出错: {vehicle_error}")
                            
                            # 车牌类别
                            if cls == 8 and recognize_plates:
                                try:
                                    # 增加一点padding
                                    padding = 5
                                    plate_x1, plate_y1 = max(x1 - padding, 0), max(y1 - padding, 0)
                                    plate_x2, plate_y2 = min(x2 + padding, frame.shape[1]), min(y2 + padding, frame.shape[0])
                                    
                                    # 裁剪车牌区域
                                    plate_img = frame[plate_y1:plate_y2, plate_x1:plate_x2]
                                    
                                    # 识别车牌文字
                                    plate_text, confidence, plate_color, bg_color = recognize_plate(plate_img, plate_ocr)
                                    
                                    if confidence > 0.3:  # 只保留置信度较高的结果
                                        plate_results.append({
                                            'frame': frame_count,
                                            'timestamp': timestamp,
                                            'box': (plate_x1, plate_y1, plate_x2, plate_y2),
                                            'text': plate_text,
                                            'conf': confidence,
                                            'color': plate_color,
                                            'bg_color': bg_color
                                        })
                                except Exception as plate_error:
                                    logger.warning(f"处理车牌出错: {plate_error}")
                        except Exception as box_error:
                            logger.error(f"处理检测框出错: {box_error}")
                            continue
                
            except torch.cuda.OutOfMemoryError:
                logger.warning("警告: CUDA内存不足，尝试清理缓存")
                torch.cuda.empty_cache()
                continue
            except Exception as e:
                logger.error(f"处理帧 {frame_count} 出错: {e}")
                continue
        
        elapsed_time = time.time() - start_time
        logger.info(f"视频处理完成, 共处理 {processed_count} 帧, 用时 {elapsed_time:.2f} 秒")
        logger.info(f"检测到 {len(vehicle_results)} 个车辆, {len(plate_results)} 个车牌")
        
    except KeyboardInterrupt:
        logger.info("处理被用户中断")
    except Exception as e:
        logger.error(f"视频处理出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 释放资源
        try:
            cap.release()
        except:
            pass
    
    return vehicle_results, plate_results

# 提取视频的关键帧
def extract_keyframes(video_path, output_folder, interval_seconds=1, max_frames=None):
    """
    从视频中按时间间隔提取关键帧
    
    参数:
        video_path: 视频文件路径
        output_folder: 关键帧保存文件夹
        interval_seconds: 提取帧的时间间隔(秒)
        max_frames: 最大提取帧数
        
    返回:
        extracted_frames: 提取的帧路径列表
    """
    # 确保输出目录存在
    os.makedirs(output_folder, exist_ok=True)
    
    # 检查视频文件
    if not os.path.exists(video_path):
        logger.error(f"错误: 视频文件不存在 {video_path}")
        return []
    
    # 读取视频
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"错误: 无法打开视频 {video_path}")
            return []
    except Exception as e:
        logger.error(f"打开视频出错: {e}")
        return []
    
    # 获取视频信息
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # 处理无效参数
    if fps <= 0:
        fps = 25  # 默认帧率
        
    if total_frames <= 0:
        total_frames = float('inf')  # 未知总帧数
        
    video_duration = total_frames / fps if total_frames != float('inf') else "未知"
    
    logger.info(f"视频信息: {fps}fps, 共{total_frames}帧, 时长{video_duration}秒")
    
    # 计算帧间隔
    frame_interval = int(fps * interval_seconds)
    if frame_interval < 1:
        frame_interval = 1
    
    # 提取帧
    extracted_frames = []
    frame_count = 0
    saved_count = 0
    
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    
    # 错误处理
    consecutive_failures = 0
    max_failures = 10
    
    # 超时设置
    start_time = time.time()
    timeout = 1800  # 30分钟
    
    try:
        while True:
            # 检查超时
            if time.time() - start_time > timeout:
                logger.warning(f"警告: 处理超时 ({timeout/60} 分钟)")
                break
                
            # 检查达到最大帧数
            if max_frames is not None and saved_count >= max_frames:
                logger.info(f"已达到最大提取帧数 {max_frames}")
                break
                
            try:
                ret, frame = cap.read()
            except Exception as e:
                logger.error(f"读取帧出错: {e}")
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    logger.error(f"连续 {max_failures} 次读取失败，终止处理")
                    break
                continue
                
            if not ret:
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    logger.error(f"连续 {max_failures} 次读取失败，终止处理")
                    break
                    
                # 如果接近视频末尾，视为正常结束  
                if total_frames != float('inf') and frame_count >= total_frames * 0.95:
                    logger.info(f"已处理视频的 {(frame_count/total_frames*100):.1f}%，视为正常完成")
                    break
                    
                time.sleep(0.1)  # 短暂暂停
                continue
                
            # 重置错误计数
            consecutive_failures = 0
            frame_count += 1
            
            # 按间隔提取
            if frame_count % frame_interval == 0:
                timestamp = frame_count / fps
                frame_path = os.path.join(output_folder, f"{video_name}_frame_{frame_count}_time_{timestamp:.2f}.jpg")
                
                try:
                    cv2.imwrite(frame_path, frame)
                    extracted_frames.append(frame_path)
                    saved_count += 1
                    
                    if saved_count % 10 == 0:  # 每10帧打印一次进度
                        logger.info(f"提取帧 {frame_count}, 时间戳: {timestamp:.2f}秒, 已保存: {saved_count} 帧")
                except Exception as save_error:
                    logger.error(f"保存帧出错: {save_error}")
        
        elapsed_time = time.time() - start_time
        logger.info(f"共提取 {saved_count} 帧, 用时 {elapsed_time:.2f} 秒")
        
    except KeyboardInterrupt:
        logger.info("提取被用户中断")
    except Exception as e:
        logger.error(f"提取关键帧出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            cap.release()
        except:
            pass
    
    return extracted_frames 

def detect_speed(frame, vehicle_detections, frame_count, fps, known_distance=15.0, focal_length=800):
    """
    估算车辆的行驶速度
    
    参数:
        frame: 视频帧
        vehicle_detections: 车辆检测结果
        frame_count: 当前帧编号
        fps: 帧率
        known_distance: 已知距离（米）
        focal_length: 焦距
    
    返回:
        带有速度标注的帧和速度信息
    """
    try:
        if not hasattr(detect_speed, "vehicle_tracker"):
            detect_speed.vehicle_tracker = {}
            detect_speed.last_speeds = {}
            
        # 创建当前帧的新跟踪字典
        current_vehicles = {}
        speeds = []
        
        # 图像高度和宽度
        height, width = frame.shape[:2]
        
        # 遍历当前帧中的每个车辆
        for vehicle in vehicle_detections:
            x1, y1, x2, y2 = [int(i) for i in vehicle["bbox"]]
            vehicle_id = vehicle.get("id", f"{x1}_{y1}_{x2}_{y2}")
            confidence = vehicle.get("confidence", 0)
            
            # 车辆在图像中的大小（以像素为单位）
            vehicle_width_px = x2 - x1
            
            # 估计车辆的实际宽度（米）- 假设普通轿车宽度约1.8米
            vehicle_width_meters = 1.8
            
            # 使用相似三角形计算距离
            # 公式: 实际距离 = (实际宽度 * 焦距) / 像素宽度
            if vehicle_width_px > 0:
                distance = (vehicle_width_meters * focal_length) / vehicle_width_px
            else:
                logger.warning(f"车辆 {vehicle_id} 的宽度为0，无法计算距离")
                continue
                
            # 添加到当前帧的跟踪字典
            current_vehicles[vehicle_id] = {
                "position": (x1, y1, x2, y2),
                "distance": distance,
                "frame": frame_count,
                "confidence": confidence
            }
            
            # 如果我们之前已经看到这辆车
            if vehicle_id in detect_speed.vehicle_tracker:
                prev_data = detect_speed.vehicle_tracker[vehicle_id]
                prev_frame = prev_data["frame"]
                prev_distance = prev_data["distance"]
                
                # 只有当与前一帧的差异足够大时才计算速度
                if frame_count - prev_frame >= 5:  # 至少5帧的差异
                    # 计算距离差
                    distance_diff = abs(prev_distance - distance)
                    
                    # 计算时间差（秒）
                    time_diff = (frame_count - prev_frame) / fps
                    
                    # 计算速度 (m/s)
                    if time_diff > 0:
                        speed_ms = distance_diff / time_diff
                        
                        # 转换为km/h
                        speed_kmh = speed_ms * 3.6
                        
                        # 应用一些过滤来避免不合理的速度
                        if 1 < speed_kmh < 150:  # 合理的速度范围
                            # 更新上一次的速度
                            detect_speed.last_speeds[vehicle_id] = speed_kmh
                            speeds.append((vehicle_id, speed_kmh))
                            
                            # 在图像上标注速度
                            label = f"{int(speed_kmh)} km/h"
                            cv2.putText(frame, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                        else:
                            logger.warning(f"车辆 {vehicle_id} 的速度估计超出合理范围: {speed_kmh:.1f} km/h")
                            # 使用上一次的合理速度（如果有）
                            if vehicle_id in detect_speed.last_speeds:
                                label = f"{int(detect_speed.last_speeds[vehicle_id])} km/h"
                                cv2.putText(frame, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                                speeds.append((vehicle_id, detect_speed.last_speeds[vehicle_id]))
                    else:
                        logger.warning(f"车辆 {vehicle_id} 的时间差为零")
                
            # 绘制车辆周围的边界框
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # 更新跟踪器
        detect_speed.vehicle_tracker = current_vehicles
        
        return frame, speeds
        
    except Exception as e:
        logger.error(f"速度检测出错: {e}")
        import traceback
        traceback.print_exc()
        return frame, [] 