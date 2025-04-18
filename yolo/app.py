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
CORS(app)  # 允许所有跨域请求
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
    client_id="yolo_detection_client",
    broker="8.138.192.81",
    port=1883,
    topic="yolo/detections"
)

# 修改服务器地址为本地地址
SERVER_URL = 'http://127.0.0.1:5000'  # 本地Flask服务器地址

# 检查GPU可用性
device = "cuda" if torch.cuda.is_available() else "cpu"
if device == "cuda":
    log_info = lambda message: print(f"[INFO] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}")
    log_info(f"使用GPU加速：{torch.cuda.get_device_name(0)}")
    # 预热GPU
    torch.cuda.empty_cache()
else:
    log_info = lambda message: print(f"[INFO] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}")
    log_info("无GPU可用，使用CPU模式")

# 初始化检测器
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
frame_skip = 2  # 每隔几帧处理一次
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

# 日志函数
def log_info(message): print(f"[INFO] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}")
def log_error(message): print(f"[ERROR] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}")

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
    
    # 预处理参数
    frame_size = (640, 480)  # 设置处理帧的大小
    
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
                    
                    # 设置视频流属性
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 减小缓冲区大小，获取最新帧

            success, frame = cap.read()
            if not success:
                log_error("读取视频帧失败")
                if cap:
                    cap.release()
                cap = None
                time.sleep(reconnect_delay)
                continue

            # 帧跳过逻辑，减少处理频率
            global frame_counter
            frame_counter += 1
            if frame_counter % frame_skip != 0:
                continue

            # 预处理图像以提高检测质量
            # 1. 缩放图像到合适大小
            frame = cv2.resize(frame, frame_size, interpolation=cv2.INTER_AREA)
            
            # 2. 增强图像（可选，根据实际效果决定是否启用）
            # 增强对比度
            # alpha = 1.2  # 对比度增强因子
            # beta = 10    # 亮度调整
            # frame = cv2.convertScaleAbs(frame, alpha=alpha, beta=beta)
            
            # 3. 去噪（可选，适合低光环境）
            # frame = cv2.GaussianBlur(frame, (3, 3), 0)

            # 直接将帧传递给detector进行处理，启用所有检测类型
            try:
                result_image, detections = detector.detect_objects(
                    frame, 
                    conf_threshold=0.4,
                    detect_vehicles=True,
                    detect_plates=True,
                    detect_accidents=True,
                    detect_violations=True
                )
            except Exception as detect_error:
                log_error(f"检测处理异常: {str(detect_error)}")
                time.sleep(1)  # 短暂休眠后继续
                continue
            
            # 降低JPEG质量以减少数据量
            try:
                _, buffer = cv2.imencode('.jpg', result_image, [int(cv2.IMWRITE_JPEG_QUALITY), 40])
                jpg_base64 = base64.b64encode(buffer).decode('utf-8')
            except Exception as encode_error:
                log_error(f"图像编码异常: {str(encode_error)}")
                continue

            # 过滤低置信度的检测结果，只保留高置信度的结果
            filtered_detections = []
            for detection in detections:
                confidence = detection.get("confidence", 0)
                if confidence >= 0.5:  # 只保留置信度>=0.5的检测结果
                    filtered_detections.append({
                        "class": detection["class_name"],
                        "confidence": confidence,
                        "coordinates": detection["coordinates"],
                        "type": detection.get("type", "unknown"),
                        "class_id": detection.get("class_id", 0)
                    })

            # 尝试通过Socket.IO发送结果
            if sio.connected:
                try:
                    sio.emit('detection_frame', {'image': jpg_base64, 'detections': filtered_detections})
                except client_sio.exceptions.ConnectionError:
                    log_error("Socket.IO发送失败，连接已断开")
                    # 不中断主循环，继续处理视频
                except Exception as socket_error:
                    log_error(f"Socket.IO发送异常: {str(socket_error)}")
                
            # 尝试通过MQTT发布检测结果
            if mqtt_client.is_connected() and not mqtt_client.is_paused():
                try:
                    mqtt_client.publish_detection(filtered_detections, jpg_base64)
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

        # 根据检测类型设置参数
        enable_license_plate = detection_type in ['plate', 'integrated', 'general']
        enable_speed = detection_type in ['speed', 'integrated']
        
        # 安全调用detector的process_video方法并处理返回结果
        try:
            result = detector.process_video(
                input_path, 
                output_path, 
                enable_license_plate=enable_license_plate, 
                enable_speed=enable_speed
            )
            
            # 处理返回值格式兼容性
            if isinstance(result, tuple) and len(result) >= 2:
                actual_output_path, processing_results = result
            elif isinstance(result, str):
                # 如果只返回路径
                actual_output_path = result
                processing_results = []
            elif isinstance(result, bool):
                # 如果返回成功/失败状态
                if result:
                    actual_output_path = output_path
                    processing_results = []
                else:
                    raise Exception("视频处理失败")
            else:
                # 默认情况
                actual_output_path = output_path
                processing_results = []
                
            # 确保输出路径有效
            if not actual_output_path or not os.path.exists(actual_output_path):
                actual_output_path = output_path
                log_error(f"视频处理返回的输出路径无效，使用默认输出路径: {output_path}")
                
            # 确保处理结果是列表
            if not isinstance(processing_results, list):
                processing_results = []
                log_warning("视频处理未返回有效的处理结果列表")
                
        except Exception as process_error:
            log_error(f"调用视频处理失败: {str(process_error)}")
            # 尝试直接调用视频处理器模块
            from detection.video_processor import process_video
            
            # 直接调用process_video函数
            log_info("尝试使用备用方法处理视频...")
            actual_output_path, processing_results = process_video(
                input_path, 
                output_path, 
                detector=detector, 
                enable_license_plate=enable_license_plate, 
                enable_speed=enable_speed
            )
        
        # 后处理视频
        try:
            temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{unique_id}.mp4")
            ffmpeg_cmd = f"ffmpeg -i {actual_output_path} -c:v libx264 -preset medium -movflags faststart {temp_path} -y -loglevel warning"
            log_info(f"执行ffmpeg命令: {ffmpeg_cmd}")
            exit_code = os.system(ffmpeg_cmd)
            
            if exit_code == 0:
                os.replace(temp_path, actual_output_path)
                log_info("元数据优化成功")
            else:
                log_error(f"ffmpeg处理失败，退出码：{exit_code}")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
        except Exception as e:
            log_error(f"元数据处理失败: {str(e)}（视频仍可下载，但可能无法流式播放）")
        
        # 提取处理结果
        detections = []
        for result in processing_results:
            if isinstance(result, dict):
                license_plates = result.get('license_plates', [])
                if license_plates:
                    detections.append({
                        'frame': result.get('frame', 0),
                        'detections': license_plates
                    })
                # 检查是否有车辆检测结果
                vehicles = result.get('vehicles', [])
                if vehicles and detection_type in ['general', 'vehicle', 'integrated']:
                    if not any(d.get('frame') == result.get('frame', 0) for d in detections):
                        detections.append({
                            'frame': result.get('frame', 0),
                            'detections': vehicles
                        })
        
        download_url = f"/download/{os.path.basename(actual_output_path)}"
        streaming_url = f"/stream/{os.path.basename(actual_output_path)}"
        threading.Thread(target=cleanup_temp_files).start()
        
        # 发布视频处理结果到MQTT
        if mqtt_client.is_connected() and not mqtt_client.is_paused():
            # 检查处理结果中是否有需要发送命令的事件
            for result in processing_results:
                if not isinstance(result, dict):
                    continue
                    
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
                'detections': detections,
                'video_url': download_url
            }
            mqtt_client.publish_detection(mqtt_data, None)
        
        return jsonify({
            'status': '处理完成',
            'detection_type': detection_type,
            'detections': detections,
            'download_url': download_url,
            'stream_url': streaming_url,
            'total_frames': len(processing_results) if isinstance(processing_results, list) else 0,
            'processing_time': time.time() - os.path.getctime(input_path)
        })
    except Exception as e:
        log_error(f"视频处理失败: {str(e)}")
        import traceback
        traceback.print_exc()
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
    if mqtt_client.connect():
        log_info("MQTT客户端已连接")
    else:
        log_error("MQTT客户端连接失败")
    
    video_stream_thread = threading.Thread(
        target=process_stream, 
        args=('rtmp://127.0.0.1/live/livestream',), 
        daemon=True
    )
    video_stream_thread.start()
    
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
        log_info("加载车牌专用检测器 (hytt.onnx)")
        if os.path.exists("models/hytt.onnx"):
            plate_detector = detection.get_detector("models/hytt.onnx", device=device, conf_threshold=0.35)
        else:
            log_error("未找到车牌专用模型，使用通用模型代替")
            plate_detector = detector
    return plate_detector

def get_accident_detector():
    global accident_detector
    if accident_detector is None:
        log_info("加载事故专用检测器 (zhlkv2.onnx)")
        if os.path.exists("models/zhlkv2.onnx"):
            accident_detector = detection.get_detector("models/zhlkv2.onnx", device=device, conf_threshold=0.4)
        else:
            log_error("未找到事故专用模型，使用通用模型代替") 
            accident_detector = detector
    return accident_detector

# 增加专门用于车辆检测的视频处理API
@app.route('/vehicle_video_detect', methods=['POST'])
def vehicle_video_detect():
    try:
        if 'video' not in request.files:
            return jsonify({'error': '未接收到视频文件'}), 400
            
        file = request.files['video']
        if file.filename == '':
            return jsonify({'error': '未选择文件'}), 400
            
        if not allowed_file(file.filename):
            return jsonify({'error': '不支持的文件类型'}), 400
        
        # 获取额外参数
        conf_threshold = float(request.form.get('confidence', 0.4))  # 置信度阈值
        skip_frames = int(request.form.get('skip_frames', 3))  # 跳过的帧数，提高处理速度
        vehicle_only = request.form.get('vehicle_only', 'true').lower() == 'true'  # 是否只检测车辆
        
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        # 保存上传的视频文件
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        unique_id = uuid.uuid4().hex
        input_filename = f"vehicle_detect_{unique_id}.{file_ext}"
        output_filename = f"vehicle_result_{unique_id}.mp4"
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)

        file.save(input_path)
        log_info(f"车辆检测视频已保存: {input_filename}")

        # 创建处理参数
        process_params = {
            'skip_frames': skip_frames,
            'batch_size': 4,  # 批处理大小，适中的值有助于提高性能
            'enable_license_plate': not vehicle_only,  # 如果只检测车辆则禁用车牌检测
            'enable_speed': False,  # 默认不启用速度检测，速度检测需要额外计算
            'conf_threshold': conf_threshold  # 设置置信度阈值
        }
        
        # 调用视频处理函数
        try:
            from detection.video_processor import process_video
            
            log_info(f"开始进行车辆视频检测，参数: {process_params}")
            
            actual_output_path, processing_results = process_video(
                input_path, 
                output_path, 
                detector=detector, 
                **process_params
            )
            
            # 确保输出路径有效
            if not actual_output_path or not os.path.exists(actual_output_path):
                actual_output_path = output_path
                log_error(f"视频处理返回的输出路径无效，使用默认输出路径: {output_path}")
                
        except Exception as process_error:
            log_error(f"车辆视频处理失败: {str(process_error)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'车辆视频处理失败: {str(process_error)}'}), 500
        
        # 优化视频以适合流式播放
        try:
            temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{unique_id}.mp4")
            ffmpeg_cmd = f"ffmpeg -i {actual_output_path} -c:v libx264 -preset fast -movflags faststart {temp_path} -y -loglevel warning"
            log_info(f"执行ffmpeg命令: {ffmpeg_cmd}")
            exit_code = os.system(ffmpeg_cmd)
            
            if exit_code == 0:
                os.replace(temp_path, actual_output_path)
                log_info("视频优化成功")
            else:
                log_error(f"ffmpeg处理失败，退出码：{exit_code}")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        except Exception as e:
            log_error(f"视频优化失败: {str(e)}（视频仍可下载，但可能无法流式播放）")
        
        # 提取车辆检测结果
        vehicle_detections = []
        vehicle_types = {}  # 统计不同类型车辆数量
        vehicle_colors = {}  # 统计不同颜色车辆数量
        
        for result in processing_results:
            if isinstance(result, dict) and 'vehicles' in result:
                vehicles = result.get('vehicles', [])
                frame = result.get('frame', 0)
                
                frame_vehicles = []
                for vehicle in vehicles:
                    # 提取车辆信息
                    vehicle_type = vehicle.get('type', '未知')
                    vehicle_color = vehicle.get('color', '未知')
                    confidence = vehicle.get('conf', 0.0)
                    
                    # 统计车辆类型
                    if vehicle_type in vehicle_types:
                        vehicle_types[vehicle_type] += 1
                    else:
                        vehicle_types[vehicle_type] = 1
                        
                    # 统计车辆颜色
                    if vehicle_color in vehicle_colors:
                        vehicle_colors[vehicle_color] += 1
                    else:
                        vehicle_colors[vehicle_color] = 1
                    
                    # 只保留需要的字段减小数据量
                    frame_vehicles.append({
                        'type': vehicle_type,
                        'color': vehicle_color,
                        'conf': confidence,
                        'box': vehicle.get('box', [0, 0, 0, 0])
                    })
                
                if frame_vehicles:
                    vehicle_detections.append({
                        'frame': frame,
                        'vehicles': frame_vehicles
                    })
        
        # 统计检测结果
        total_vehicles = sum(vehicle_types.values())
        
        # 准备返回数据
        download_url = f"/download/{os.path.basename(actual_output_path)}"
        streaming_url = f"/stream/{os.path.basename(actual_output_path)}"
        
        # 清理临时文件
        threading.Thread(target=cleanup_temp_files).start()
        
        # 如果启用了MQTT，发送检测汇总信息
        if mqtt_client.is_connected() and not mqtt_client.is_paused():
            # 发送汇总数据
            summary_data = {
                'detection_type': 'vehicle',
                'total_vehicles': total_vehicles,
                'vehicle_types': vehicle_types,
                'vehicle_colors': vehicle_colors,
                'video_url': download_url
            }
            mqtt_client.publish_detection(summary_data, None)
        
        # 返回结果
        return jsonify({
            'status': '车辆检测完成',
            'total_vehicles': total_vehicles,
            'vehicle_types': vehicle_types,
            'vehicle_colors': vehicle_colors,
            'detections': vehicle_detections[:100],  # 只返回前100帧的检测结果，避免数据过大
            'download_url': download_url,
            'stream_url': streaming_url,
            'processing_info': {
                'total_frames_processed': len(processing_results),
                'processing_time': time.time() - os.path.getctime(input_path),
                'conf_threshold': conf_threshold,
                'skip_frames': skip_frames
            }
        })
    except Exception as e:
        log_error(f"车辆检测失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'车辆检测失败: {str(e)}'}), 500