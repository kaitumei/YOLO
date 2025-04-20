from flask import Flask, render_template, request, jsonify, Response, send_from_directory, send_file
import cv2
import numpy as np
import base64
import os
import torch
from datetime import datetime
import threading
import socketio as client_sio
from flask_socketio import SocketIO as FlaskSocketIO
import time
import psutil
from werkzeug.utils import secure_filename
import uuid
from flask_cors import CORS  # 添加在文件顶部
import re 
import detection  # 导入新的集成检测模块
from utils.mqtt_module import MQTTModule  # 导入MQTT模块
import json

# 初始化Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'temp_videos'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)  # 允许所有跨域请求并支持凭证
# 初始化Socket
socketio = FlaskSocketIO(app, cors_allowed_origins="*")
sio = client_sio.Client(
    reconnection=True, 
    reconnection_attempts=5, 
    reconnection_delay=1000,
    request_timeout=10,  # 减少请求超时时间
    http_session=None,  # 不使用会话
    logger=False,  # 禁用日志
    engineio_logger=False  # 禁用Engine.IO日志
)

# 初始化MQTT模块
mqtt_client = MQTTModule(
    client_id="dawdawdw",
    broker="117.72.120.52",
    port=1883,
    topic="alarm/command"
)

# 修改服务器地址为本地地址
SERVER_URL = 'http://127.0.0.1:5000'  # 本地Flask服务器地址

# 检查GPU可用性
device = "cuda" if torch.cuda.is_available() else "cpu"
if device == "cuda":
    log_info = lambda message: print(f"[INFO] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}")
    log_info(f"使用GPU加速：{torch.cuda.get_device_name(0)}")
    # 预热GPU并优化内存使用
    torch.cuda.empty_cache()
    
    # 设置GPU优化参数
    torch.backends.cudnn.benchmark = True  # 启用cudnn自动优化
    torch.backends.cudnn.deterministic = False  # 关闭确定性模式以提高性能
    torch.backends.cudnn.enabled = True  # 确保cudnn启用
    
    # 设置内存分配策略，减少内存碎片
    if hasattr(torch.cuda, 'memory_stats'):
        log_info("启用高级内存优化")
        torch.cuda.set_per_process_memory_fraction(0.8)  # 限制使用80%的GPU内存，避免OOM
        if hasattr(torch.cuda, 'empty_cache'):
            # 定期清理GPU内存的函数
            def clean_gpu_memory():
                torch.cuda.empty_cache()
                log_info("GPU内存已清理")
            
            # 创建定时清理GPU内存的线程
            import threading
            gpu_cleaner = threading.Timer(300.0, clean_gpu_memory)  # 每5分钟清理一次
            gpu_cleaner.daemon = True
            gpu_cleaner.start()
    
    log_info("已启用CUDA优化设置，提高GPU性能")
else:
    log_info = lambda message: print(f"[INFO] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}")
    log_info("无GPU可用，使用CPU模式")

# 初始化检测器
# 统一使用zhlkv3.onnx模型，并利用GPU加速
log_info("使用统一的zhlkv3.onnx模型初始化检测器")
detector = detection.get_detector("models/zhlkv3.onnx", device=device)

# 添加专用检测器
plate_detector = None  # 车牌专用检测器
accident_detector = None  # 事故专用检测器

# 全局变量
pause_flag = False
detected_objects = []
processing_lock = threading.Lock()
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}

# 添加帧处理控制变量
frame_skip = 3  # 每3帧处理1帧，提高帧率
frame_counter = 0  # 帧计数器

# 添加WebSocket连接优化
sio = client_sio.Client(
    reconnection=True, 
    reconnection_attempts=5, 
    reconnection_delay=1000,
    request_timeout=10,  # 减少请求超时时间
    http_session=None,  # 不使用会话
    logger=False,  # 禁用日志
    engineio_logger=False  # 禁用Engine.IO日志
)

# 添加缓冲区管理
frame_buffer = []
MAX_BUFFER_SIZE = 5  # 最大缓冲区大小

# 添加视频质量设置变量，用于动态调整质量
video_quality = {
    'width': 640,  # 默认使用较低分辨率提高帧率
    'height': 360,
    'quality': 75  # 默认使用较低的JPEG质量以减少传输数据量
}

# 修改batch_size设置
batch_processing = {
    'enabled': True,
    'max_size': 4,  # 最大批处理大小
    'buffer': []    # 批处理缓冲区
}

# 修改推理设置，只检测重要目标
detection_settings = {
    'detect_vehicles': True,  # 保持车辆检测
    'detect_plates': False,   # 默认关闭车牌检测以提高性能
    'detect_accidents': True, # 保持事故检测
    'detect_violations': False, # 默认关闭违章检测以提高性能
    'conf_threshold': 0.4     # 提高置信度阈值以减少处理目标数量
}

# 日志函数
def log_info(message): print(f"[INFO] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}")
def log_error(message): print(f"[ERROR] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}")

# 处理特定类型检测结果的MQTT发布
def publish_special_detection(detections):
    """向MQTT发布特定类型的检测结果"""
    if not mqtt_client.is_connected() or mqtt_client.is_paused():
        return
        
    for detection in detections:
        class_name = detection.get("class_name", "")
        detection_type = detection.get("type", "")
        
        # 只检测accident（事故）
        if "accident" in class_name.lower() or "accident" in detection_type.lower():
            try:
                mqtt_client.publish_command("accident")
                log_info("MQTT已发送事故警报")
            except Exception as e:
                log_error(f"MQTT发送事故警报失败: {str(e)}")

# 添加全局错误处理
@app.errorhandler(Exception)
def handle_exception(e):
    """全局异常处理器"""
    log_error(f"请求处理异常: {str(e)}")
    return jsonify({"error": "服务器内部错误", "message": str(e)}), 500

# 处理连接重置错误
@socketio.on_error()
def error_handler(e):
    """SocketIO错误处理器"""
    log_error(f"SocketIO错误: {str(e)}")
    return False  # 阻止异常传播

@socketio.on_error_default
def default_error_handler(e):
    """SocketIO默认错误处理器"""
    log_error(f"SocketIO默认错误: {str(e)}")
    return False  # 阻止异常传播

# Socket.IO事件处理
@sio.event
def connect(): log_info("成功连接到外部服务器")
@sio.event
def connect_error(data): log_error(f"连接失败: {data}")
@sio.event
def disconnect(): log_info("与外部服务器断开连接")

# 辅助函数
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def cleanup_temp_files():
    """清理超过1小时的临时文件"""
    now = time.time()
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.isfile(file_path):
            if (now - os.path.getctime(file_path)) > 3600:  # 1小时
                try:
                    os.remove(file_path)
                    log_info(f"清理临时文件: {filename}")
                except Exception as e:
                    log_error(f"清理文件失败 {filename}: {str(e)}")

# 实时视频流处理 - 使用detection模块
def process_stream(stream_url):
    cap = None
    reconnect_count = 0
    max_reconnects = 10
    reconnect_delay = 3
    error_count = 0  # 错误计数器
    frame_counter = 0  # 帧计数器重置
    
    # 添加FPS计算相关变量
    fps_start_time = time.time()
    fps_frame_count = 0
    fps_value = 0
    
    # 添加帧缓存，避免渲染上一帧
    prev_frame = None
    
    while True:
        try:
            if cap is None or not cap.isOpened():
                log_info(f"尝试连接视频流: {stream_url}")
                cap = cv2.VideoCapture(stream_url)
                if not cap.isOpened():
                    reconnect_count += 1
                    log_error(f"无法打开视频流 (尝试 {reconnect_count}/{max_reconnects})")
                    if reconnect_count >= max_reconnects:
                        log_info("达到最大重连次数，休眠60秒后重试")
                        time.sleep(60)
                        reconnect_count = 0
                    else:
                        time.sleep(reconnect_delay)
                    continue
                else:
                    reconnect_count = 0
                    error_count = 0  # 连接成功，重置错误计数
                    log_info("视频流连接成功")
                    
                    # 优化视频流属性
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)  # 减小缓冲区大小以减少延迟
                    # 设置较低的分辨率以提高帧率
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, video_quality['width'])
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, video_quality['height'])
                    # 尝试设置较高的摄像头FPS（如果摄像头支持）
                    cap.set(cv2.CAP_PROP_FPS, 30)

            success, frame = cap.read()
            if not success:
                log_error("读取视频帧失败")
                if cap:
                    cap.release()
                cap = None
                time.sleep(reconnect_delay)
                continue

            # 帧跳过逻辑，提高处理效率
            frame_counter += 1
            
            # 计算实际FPS
            fps_frame_count += 1
            current_time = time.time()
            elapsed = current_time - fps_start_time
            
            if elapsed >= 2.0:  # 每2秒更新一次FPS
                fps_value = fps_frame_count / elapsed
                # log_info(f"当前视频处理帧率: {fps_value:.2f} FPS")  # 注释掉FPS日志输出
                fps_frame_count = 0
                fps_start_time = current_time
            
            # 根据设置的帧跳过率处理帧
            if frame_counter % frame_skip != 0:
                continue

            # 计算当前需要使用的帧尺寸，根据当前质量设置调整
            current_frame_size = (video_quality['width'], video_quality['height'])
            
            # 高效预处理图像 - 只缩放到所需大小
            frame = cv2.resize(frame, current_frame_size, interpolation=cv2.INTER_AREA)
            
            # 检查帧是否与上一帧相同（避免重复发送相同帧）
            if prev_frame is not None:
                # 计算帧差异
                frame_diff = cv2.absdiff(frame, prev_frame)
                if frame_diff.mean() < 1.0:  # 如果帧几乎没有变化，跳过这一帧
                    continue
            
            # 更新前一帧
            prev_frame = frame.copy()
            
            # 使用优化的检测设置
            conf_threshold = detection_settings['conf_threshold']
            
            # 直接将帧传递给detector进行处理，根据设置启用检测类型
            try:
                result_image, detections = detector.detect_objects(
                    frame, 
                    conf_threshold=conf_threshold,
                    detect_vehicles=detection_settings['detect_vehicles'],
                    detect_plates=detection_settings['detect_plates'],
                    detect_accidents=detection_settings['detect_accidents'],
                    detect_violations=detection_settings['detect_violations']
                )
            except Exception as detect_error:
                log_error(f"检测处理异常: {str(detect_error)}")
                time.sleep(0.2)  # 减少休眠时间
                continue
            
            # 使用优化的JPEG质量设置
            try:
                # 使用更高质量设置，降低压缩伪影
                encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), video_quality['quality'], 
                                int(cv2.IMWRITE_JPEG_OPTIMIZE), 1]
                _, buffer = cv2.imencode('.jpg', result_image, encode_params)
                jpg_base64 = base64.b64encode(buffer).decode('utf-8')
            except Exception as encode_error:
                log_error(f"图像编码异常: {str(encode_error)}")
                continue

            # 过滤低置信度的检测结果，只保留高置信度的结果
            filtered_detections = []
            for detection in detections:
                confidence = detection.get("confidence", 0)
                if confidence >= conf_threshold:  # 使用全局设置的置信度阈值
                    filtered_detections.append({
                        "class": detection["class_name"],
                        "confidence": confidence,
                        "coordinates": detection["coordinates"],
                        "type": detection.get("type", "unknown"),
                        "class_id": detection.get("class_id", 0)
                    })

            # 添加FPS信息到数据中
            detection_data = {
                'image': jpg_base64, 
                'detections': filtered_detections,
                'fps': round(fps_value, 1),
                'timestamp': int(time.time() * 1000)  # 添加时间戳防止浏览器缓存
            }

            # 尝试通过Socket.IO发送结果
            if sio.connected:
                try:
                    sio.emit('detection_frame', detection_data)
                except client_sio.exceptions.ConnectionError:
                    log_error("Socket.IO发送失败，连接已断开")
                    # 不中断主循环，继续处理视频
                except Exception as socket_error:
                    log_error(f"Socket.IO发送异常: {str(socket_error)}")
                
            # 尝试通过MQTT发布检测结果
            if mqtt_client.is_connected() and not mqtt_client.is_paused():
                try:
                    mqtt_client.publish_detection(filtered_detections, jpg_base64)
                    # 发布特定类型的检测结果
                    publish_special_detection(filtered_detections)
                except Exception as mqtt_error:
                    log_error(f"MQTT发布异常: {str(mqtt_error)}")
                    
            # 成功处理一帧，重置错误计数
            error_count = 0
            
        except Exception as e:
            error_count += 1
            log_error(f"视频流处理异常: {str(e)}")
            if error_count > 5:
                log_error("连续错误过多，重新初始化视频捕获")
                if cap:
                    cap.release()
                cap = None
                error_count = 0
            time.sleep(reconnect_delay)

# 添加接收质量设置事件处理
@sio.on('video_quality_updated')
def handle_quality_update(data):
    """处理从服务器接收的视频质量更新"""
    global video_quality, frame_skip
    try:
        # 更新视频质量设置
        if 'quality' in data:
            quality_map = {
                'HIGH': {'width': 1280, 'height': 720, 'quality': 85},
                'MEDIUM': {'width': 854, 'height': 480, 'quality': 80},
                'LOW': {'width': 640, 'height': 360, 'quality': 70}
            }
            
            if data['quality'] in quality_map:
                new_settings = quality_map[data['quality']]
                video_quality.update(new_settings)
                log_info(f"视频质量已更新为: {data['quality']}, 分辨率: {video_quality['width']}x{video_quality['height']}, JPEG质量: {video_quality['quality']}")
            else:
                # 使用接收到的具体数值
                video_quality.update({
                    'width': int(data.get('width', video_quality['width'])),
                    'height': int(data.get('height', video_quality['height'])),
                    'quality': int(data.get('jpegQuality', 0.9) * 100)  # 转换0-1范围为0-100
                })
                log_info(f"视频质量已更新, 分辨率: {video_quality['width']}x{video_quality['height']}, JPEG质量: {video_quality['quality']}")
        
        # 更新帧跳过率设置
        if 'frameSkip' in data:
            new_frame_skip = int(data.get('frameSkip', 3))
            if 1 <= new_frame_skip <= 10:  # 限制在合理范围内
                frame_skip = new_frame_skip
                log_info(f"跳帧率已更新为: {frame_skip}")
                
                # 同时更新检测设置，根据跳帧率优化
                if frame_skip >= 5:
                    # 高跳帧率时，使用更高的置信度阈值和更少的检测目标
                    detection_settings['conf_threshold'] = 0.45
                    detection_settings['detect_plates'] = False
                    detection_settings['detect_violations'] = False
                elif frame_skip >= 3:
                    # 中等跳帧率，平衡设置
                    detection_settings['conf_threshold'] = 0.4
                    detection_settings['detect_plates'] = False
                    detection_settings['detect_violations'] = False
                else:
                    # 低跳帧率，保持更多的检测功能
                    detection_settings['conf_threshold'] = 0.35
                    detection_settings['detect_plates'] = True
                    detection_settings['detect_violations'] = True
    except Exception as e:
        log_error(f"更新视频质量设置失败: {str(e)}")

# API端点 - 图像检测 - 使用detection模块
@app.route('/img_predict', methods=['POST'])
def img_predict():
    try:
        data = request.json
        image_base64 = data.get('image')
        detection_type = data.get('type', 'general') # 检测类型参数: 'general', 'vehicle', 'plate', 'accident', 'violation'
        
        # 设置检测配置
        detect_vehicles = True  # 默认检测车辆
        detect_plates = True    # 默认检测车牌
        detect_accidents = True # 默认检测事故
        detect_violations = True # 默认检测违章行为
        
        # 根据检测类型调整设置
        if detection_type == 'vehicle':
            detect_plates = False
            detect_accidents = False
            detect_violations = False
        elif detection_type == 'plate':
            detect_vehicles = False
            detect_accidents = False
            detect_violations = False
        elif detection_type == 'accident':
            detect_vehicles = False
            detect_plates = False
            detect_violations = False
        elif detection_type == 'violation':
            detect_vehicles = False
            detect_plates = False
            detect_accidents = False
        
        if not image_base64:
            return jsonify({'error': '未接收到图像数据'}), 400
            
        # 解码Base64图像
        try:
            image_data = base64.b64decode(image_base64)
            image = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)
            
            if image is None:
                return jsonify({'error': '无法解码图像数据'}), 400
                
            # 保存输入图像用于调试
            if detection_type == 'plate':
                debug_path = f"plate_input_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
                cv2.imwrite(debug_path, image)
                log_info(f"已保存车牌输入图像: {debug_path}")
        except Exception as e:
            log_error(f"解码图像失败: {e}")
            return jsonify({'error': '解码图像失败'}), 400
        
        # 选择合适的检测器
        current_detector = detector  # 默认使用通用检测器
        conf_threshold = 0.3  # 默认置信度阈值
        
        if detection_type == 'plate':
            current_detector = get_plate_detector()
            conf_threshold = 0.35  # 提高车牌检测的置信度阈值，减少误检
        elif detection_type == 'accident':
            current_detector = get_accident_detector() 
            conf_threshold = 0.4   # 提高事故检测的置信度阈值
        
        # 根据检测类型调用不同的detector方法
        if detection_type == 'plate':
            # 调用车牌检测方法
            result_image, detections = current_detector.detect_license_plate(image, conf_threshold=conf_threshold)
        elif detection_type == 'accident':
            # 调用事故检测方法
            result_image, detections = current_detector.detect_accident(image, conf_threshold=conf_threshold)
        elif detection_type == 'violation':
            # 调用违章检测方法
            result_image, detections = current_detector.detect_violation(image, conf_threshold=conf_threshold)
        elif detection_type == 'vehicle':
            # 调用车辆检测方法，只启用车辆检测
            result_image, detections = current_detector.detect_objects(
                image, 
                conf_threshold=conf_threshold,
                detect_vehicles=True,
                detect_plates=False,
                detect_accidents=False,
                detect_violations=False
            )
        else:
            # 调用通用检测方法，传递特定的检测参数
            result_image, detections = current_detector.detect_objects(
                image, 
                conf_threshold=conf_threshold,
                detect_vehicles=detect_vehicles,
                detect_plates=detect_plates,
                detect_accidents=detect_accidents,
                detect_violations=detect_violations
            )
        
        # 如果检测失败
        if result_image is None:
            return jsonify({'error': '处理图像失败'}), 500
        
        # 将结果图像转回Base64
        _, buffer = cv2.imencode('.jpg', result_image, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        result_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # 发布检测结果到MQTT
        if mqtt_client.is_connected() and not mqtt_client.is_paused():
            try:
                mqtt_client.publish_detection(detections, result_base64)
                # 发布特定类型的检测结果
                publish_special_detection(detections)
            except Exception as mqtt_error:
                log_error(f"MQTT发布异常: {str(mqtt_error)}")
        
        return jsonify({
            'result': result_base64,
            'detections': detections  
        })
    except Exception as e:
        log_error(f"图像检测失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'处理失败: {str(e)}'}), 500

# API端点 - 视频检测 - 使用detection模块
@app.route('/video_predict', methods=['POST'])
def video_predict():
    try:
        if 'video' not in request.files:
            return jsonify({'error': '未接收到视频文件'}), 400
            
        file = request.files['video']
        if file.filename == '':
            return jsonify({'error': '未选择文件'}), 400
            
        if not allowed_file(file.filename):
            return jsonify({'error': '不支持的文件类型'}), 400

        # 获取检测类型
        detection_type = request.form.get('type', 'general')  # 'general', 'plate', 'speed', 'integrated'
        
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        unique_id = uuid.uuid4().hex
        input_filename = f"input_{unique_id}.{file_ext}"
        output_filename = f"output_{unique_id}.mp4"
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)

        file.save(input_path)
        log_info(f"视频文件已保存: {input_filename}")

        # 记录开始时间用于计算处理用时
        start_time = time.time()

        # 根据检测类型设置参数
        enable_license_plate = detection_type in ['plate', 'integrated', 'general']
        enable_speed = detection_type in ['speed', 'integrated']
        
        # 直接调用detector的process_video方法
        output_path, processing_results = detector.process_video(
            input_path, 
            output_path, 
            enable_license_plate=enable_license_plate, 
            enable_speed=enable_speed
        )
        
        # 计算处理时间
        processing_time = int(time.time() - start_time)
        
        # 后处理视频
        try:
            temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{unique_id}.mp4")
            ffmpeg_cmd = f"ffmpeg -i {output_path} -c:v libx264 -preset medium -movflags faststart {temp_path} -y -loglevel warning"
            log_info(f"执行ffmpeg命令: {ffmpeg_cmd}")
            exit_code = os.system(ffmpeg_cmd)
            
            if exit_code == 0:
                os.replace(temp_path, output_path)
                log_info("元数据优化成功")
            else:
                log_error(f"ffmpeg处理失败，退出码：{exit_code}")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
        except Exception as e:
            log_error(f"元数据处理失败: {str(e)}（视频仍可下载，但可能无法流式播放）")
        
        # 优化检测结果的格式，确保与前端期望的格式一致
        formatted_detections = []
        all_objects = []  # 用于收集所有检测到的对象
        
        # 将每帧的检测结果重新组织为前端可识别的格式
        for result in processing_results:
            frame_detections = []
            
            # 处理车辆检测结果
            if 'vehicles' in result and result['vehicles']:
                for vehicle in result['vehicles']:
                    detection_obj = {
                        'class_name': vehicle.get('class_name', '车辆'),
                        'type': 'vehicle',
                        'confidence': vehicle.get('confidence', 0.0),
                        'coordinates': vehicle.get('coordinates', [])
                    }
                    frame_detections.append(detection_obj)
                    all_objects.append(detection_obj)
            
            # 处理车牌检测结果
            if 'license_plates' in result and result['license_plates']:
                for plate in result['license_plates']:
                    detection_obj = {
                        'class_name': '车牌',
                        'type': 'license_plate',
                        'confidence': plate.get('confidence', 0.0),
                        'coordinates': plate.get('coordinates', [])
                    }
                    if 'text' in plate:
                        detection_obj['plate_text'] = plate['text']
                    frame_detections.append(detection_obj)
                    all_objects.append(detection_obj)
            
            # 处理事故检测结果
            if 'accidents' in result and result['accidents']:
                for accident in result['accidents']:
                    detection_obj = {
                        'class_name': '事故',
                        'type': 'accident',
                        'confidence': accident.get('confidence', 0.0),
                        'coordinates': accident.get('coordinates', [])
                    }
                    frame_detections.append(detection_obj)
                    all_objects.append(detection_obj)
            
            # 处理违章检测结果
            if 'violations' in result and result['violations']:
                for violation in result['violations']:
                    detection_obj = {
                        'class_name': violation.get('type', '违章'),
                        'type': 'violation',
                        'confidence': violation.get('confidence', 0.0),
                        'coordinates': violation.get('coordinates', [])
                    }
                    frame_detections.append(detection_obj)
                    all_objects.append(detection_obj)
            
            # 处理超速检测结果
            if 'speed_tracking' in result and result['speed_tracking']:
                for track in result['speed_tracking']:
                    detection_obj = {
                        'class_name': '超速',
                        'type': 'overspeed',
                        'confidence': 1.0,  # 默认置信度
                        'coordinates': track.get('bbox', []),
                        'speed': track.get('speed', 0)
                    }
                    frame_detections.append(detection_obj)
                    all_objects.append(detection_obj)
            
            # 只有当有检测结果时才添加到总结果中
            if frame_detections:
                formatted_detections.append({
                    'frame': result.get('frame', 0),
                    'detections': frame_detections
                })
        
        # 如果没有检测到任何对象，确保返回一些默认数据以便前端正确显示
        if not all_objects:
            # 添加常见类别的空检测数据，确保前端可以显示类别列表
            default_classes = [
                {'class_name': '小汽车', 'type': 'vehicle'},
                {'class_name': '公交车', 'type': 'vehicle'},
                {'class_name': '卡车', 'type': 'vehicle'},
                {'class_name': '车牌', 'type': 'license_plate'},
                {'class_name': '事故', 'type': 'accident'},
                {'class_name': '违停', 'type': 'violation'}
            ]
            
            for cls in default_classes:
                all_objects.append({
                    'class_name': cls['class_name'],
                    'type': cls['type'],
                    'confidence': 0.0,
                    'coordinates': []
                })
        
        download_url = f"/download/{output_filename}"
        threading.Thread(target=cleanup_temp_files).start()
        
        # 发布视频处理结果到MQTT
        if mqtt_client.is_connected() and not mqtt_client.is_paused():
            # 检查处理结果中是否有需要发送命令的事件
            for result in processing_results:
                # 检查事故
                if result.get('accidents'):
                    mqtt_client.publish_command('accident')
                
                # 检查违章停车
                if result.get('illegal_parking'):
                    mqtt_client.publish_command('illegal_parkin')
                
                # 检查超速
                if result.get('speed_tracking'):
                    for track in result.get('speed_tracking', []):
                        if track.get('speed', 0) > track.get('speed_limit', 60):  # 假设默认限速60
                            mqtt_client.publish_command('overspeed')
                            break
            
            # 提取关键信息以避免发送过大的数据
            mqtt_data = {
                'detection_type': detection_type,
                'detections': formatted_detections,
                'video_url': download_url
            }
            mqtt_client.publish_detection(mqtt_data, None)
        
        # 为了与前端兼容，将所有检测到的对象直接放到detections数组中
        return jsonify({
            'status': '处理完成',
            'detection_type': detection_type,
            'detections': all_objects,  # 直接返回所有检测到的对象
            'download_url': download_url,
            'stream_url': f"/stream/{output_filename}",
            'processing_time': processing_time  # 添加处理时间
        })
    except Exception as e:
        log_error(f"视频处理失败: {str(e)}")
        return jsonify({'error': f'视频处理失败: {str(e)}'}), 500

# 添加日志警告函数
def log_warning(message): print(f"[WARNING] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}")

# 文件下载端点（保持原下载功能）
@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    try:
        return send_from_directory(
            directory=app.config['UPLOAD_FOLDER'],
            path=filename,
            as_attachment=True,
            download_name=f"processed_{filename}"
        )
    except FileNotFoundError:
        return jsonify({'error': '文件不存在或已过期'}), 404

@app.route('/stream/<filename>')
def stream_video(filename):
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    # 验证文件存在
    if not os.path.exists(video_path):
        return jsonify({'error': '文件不存在'}), 404
    
    # 获取文件大小
    file_size = os.path.getsize(video_path)
    
    # 处理范围请求
    range_header = request.headers.get('Range', None)
    byte1, byte2 = 0, None
    
    if range_header:
        match = re.search(r'bytes=(\d+)-(\d*)', range_header)
        if match:
            groups = match.groups()
            byte1 = int(groups[0]) if groups[0] else 0
            byte2 = int(groups[1]) if groups[1] else file_size - 1
    
    # 设置分块大小（1MB）
    chunk_size = 1024 * 1024
    if not byte2:
        byte2 = min(byte1 + chunk_size, file_size - 1)
    
    # 计算实际需要读取的长度
    length = byte2 - byte1 + 1
    
    # 创建响应
    def generate():
        with open(video_path, 'rb') as f:
            f.seek(byte1)
            data = f.read(length)
            yield data

    response = Response(
        generate(),
        206,  # Partial Content
        mimetype='video/mp4',
        direct_passthrough=True
    )
    
    # 设置响应头
    response.headers.add('Content-Range', f'bytes {byte1}-{byte2}/{file_size}')
    response.headers.add('Accept-Ranges', 'bytes')
    response.headers.add('Content-Length', str(length))
    response.headers.add('Cache-Control', 'no-cache')
    
    return response


# API端点 - 服务器状态
@app.route('/api/status', methods=['GET'])
def server_status():
    try:
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        gpu_info = None
        try:
            if torch.cuda.is_available():
                gpu_info = {
                    'name': torch.cuda.get_device_name(0),
                    'memory_allocated': f"{torch.cuda.memory_allocated(0)/1024**3:.2f} GB",
                    'memory_reserved': f"{torch.cuda.memory_reserved(0)/1024**3:.2f} GB",
                }
        except:
            pass
            
        return jsonify({
            'cpu': f"{cpu_percent}%",
            'memory': {
                'total': f"{memory.total/1024**3:.2f} GB",
                'used': f"{memory.used/1024**3:.2f} GB",
                'percent': f"{memory.percent}%"
            },
            'disk': {
                'total': f"{disk.total/1024**3:.2f} GB",
                'used': f"{disk.used/1024**3:.2f} GB",
                'percent': f"{disk.percent}%"
            },
            'gpu': gpu_info,
            'time': datetime.now().isoformat()
        })
    except Exception as e:
        log_error(f"获取服务器状态失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 健康检查API
@app.route('/healthcheck', methods=['GET'])
def healthcheck():
    return jsonify({'status': 'healthy', 'time': datetime.now().isoformat()})

@app.route('/')
def index():
    return '有'

# 主入口
if __name__ == '__main__':
    try:
        sio.connect(SERVER_URL)  # 连接到本地Flask服务器
    except Exception as e:
        log_error(f"无法连接到本地服务器: {str(e)}")
    
    # 设置MQTT日志函数并连接
    mqtt_client.set_logger(log_info, log_error)
    
    # 尝试多次连接MQTT服务器
    mqtt_connected = False
    mqtt_retry_count = 0
    mqtt_max_retries = 5
    
    while not mqtt_connected and mqtt_retry_count < mqtt_max_retries:
        if mqtt_client.connect():
            log_info("MQTT客户端已连接")
            mqtt_connected = True
        else:
            mqtt_retry_count += 1
            log_error(f"MQTT客户端连接失败 (尝试 {mqtt_retry_count}/{mqtt_max_retries})")
            time.sleep(2)  # 等待2秒后重试
    
    if not mqtt_connected:
        log_warning("MQTT连接失败，将在后台继续尝试自动重连")
    
    # 创建视频流处理线程并设置优先级
    import threading
    video_stream_thread = threading.Thread(
        target=process_stream, 
        args=('rtmp://127.0.0.1/live/livestream',), 
        daemon=True,
        name="StreamProcessor"
    )
    # 设置为较高优先级
    video_stream_thread.start()
    
    # 设置全局异常处理
    def handle_thread_exception(args):
        log_error(f"线程异常: {args.exc_type.__name__}: {args.exc_value}")
        log_error(f"线程名称: {args.thread.name}")
        # 如果是视频流线程崩溃，尝试重新启动
        if args.thread.name == "StreamProcessor":
            log_info("尝试重新启动视频流处理线程...")
            new_thread = threading.Thread(
                target=process_stream, 
                args=('rtmp://127.0.0.1/live/livestream',), 
                daemon=True,
                name="StreamProcessor"
            )
            new_thread.start()
    
    # 设置线程异常处理器
    threading.excepthook = handle_thread_exception
    
    log_info("YOLO服务器启动中...")
    
    try:
        # 添加额外的错误处理，使服务器更加稳定
        socketio.run(app, host='127.0.0.1', port=5001, allow_unsafe_werkzeug=True, log_output=False)
    except KeyboardInterrupt:
        log_info("服务器正常关闭")
    except Exception as e:
        log_error(f"服务器异常: {str(e)}")
        import traceback
        traceback.print_exc()
        # 尝试重新启动服务器
        log_info("尝试重新启动服务器...")
        try:
            socketio.run(app, host='127.0.0.1', port=5001, allow_unsafe_werkzeug=True, log_output=False)
        except Exception as restart_error:
            log_error(f"重启失败: {str(restart_error)}")

# 延迟加载其他模型（按需加载）
def get_plate_detector():
    global plate_detector
    if plate_detector is None:
        log_info("加载车牌专用检测器 (zhlkv3.onnx)")
        if os.path.exists("models/zhlkv3.onnx"):
            plate_detector = detection.get_detector("models/zhlkv3.onnx", device=device, conf_threshold=0.35)
        else:
            log_error("未找到zhlkv3.onnx模型，使用通用模型代替")
            plate_detector = detector
    return plate_detector

def get_accident_detector():
    global accident_detector
    if accident_detector is None:
        log_info("加载事故专用检测器 (zhlkv3.onnx)")
        if os.path.exists("models/zhlkv3.onnx"):
            accident_detector = detection.get_detector("models/zhlkv3.onnx", device=device, conf_threshold=0.4)
        else:
            log_error("未找到zhlkv3.onnx模型，使用通用模型代替") 
            accident_detector = detector
    return accident_detector