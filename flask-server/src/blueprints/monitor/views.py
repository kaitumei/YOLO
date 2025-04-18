from flask import render_template, request, jsonify, current_app, Response
from flask_socketio import emit
from . import bp
from src.utils.exts import socketio
import cv2
import numpy as np
import time
import threading
import os
import logging
from datetime import datetime
import sys
import json

# 导入YOLO检测模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../yolo')))
from vehicle_detector_module import VehicleDetectorModule

# 全局变量
detector = None
camera = None
camera_lock = threading.Lock()
stream_active = False
stream_thread = None

# 初始化检测器
def initialize_detector():
    global detector
    if detector is None:
        try:
            detector = VehicleDetectorModule(
                model_path='models/ZHLK_110.pt',
                log_dir='logs',
                save_dir='detections'
            )
            current_app.logger.info("YOLO检测器初始化成功")
        except Exception as e:
            current_app.logger.error(f"YOLO检测器初始化失败: {str(e)}")

# 生成视频帧
def generate_frames():
    global camera, detector, stream_active
    
    if camera is None:
        camera = cv2.VideoCapture(0)  # 默认使用第一个摄像头
    
    frame_id = 0
    start_time = time.time()
    
    while stream_active:
        with camera_lock:
            success, frame = camera.read()
        
        if not success:
            current_app.logger.error("无法读取摄像头帧")
            break
        
        # 计算实际FPS
        current_time = time.time()
        elapsed_time = current_time - start_time
        actual_fps = frame_id / elapsed_time if elapsed_time > 0 else 0
        
        # 处理帧
        if detector:
            processed_frame, detections = detector.detect_frame(frame, frame_id, actual_fps)
        else:
            processed_frame = frame
            detections = []
        
        # 编码帧为JPEG
        ret, buffer = cv2.imencode('.jpg', processed_frame)
        if not ret:
            continue
        
        # 转换为base64
        frame_bytes = buffer.tobytes()
        frame_base64 = f"data:image/jpeg;base64,{base64.b64encode(frame_bytes).decode('utf-8')}"
        
        # 发送帧和检测结果
        socketio.emit('monitor_frame', {
            'frame': frame_base64,
            'detections': detections,
            'fps': actual_fps
        })
        
        frame_id += 1
        time.sleep(0.01)  # 控制帧率
    
    # 清理资源
    with camera_lock:
        if camera:
            camera.release()
            camera = None

# 路由
@bp.route('/')
def index():
    """实时监控首页"""
    return render_template('monitor/index.html')

@bp.route('/start')
def start_monitor():
    """启动实时监控"""
    global stream_active, stream_thread, camera
    
    if stream_active:
        return jsonify({"success": False, "message": "监控已经在运行中"})
    
    # 初始化检测器
    initialize_detector()
    
    # 启动流线程
    stream_active = True
    stream_thread = threading.Thread(target=generate_frames)
    stream_thread.daemon = True
    stream_thread.start()
    
    return jsonify({"success": True, "message": "监控已启动"})

@bp.route('/stop')
def stop_monitor():
    """停止实时监控"""
    global stream_active, camera
    
    if not stream_active:
        return jsonify({"success": False, "message": "监控未在运行"})
    
    stream_active = False
    
    # 释放摄像头
    with camera_lock:
        if camera:
            camera.release()
            camera = None
    
    return jsonify({"success": True, "message": "监控已停止"})

@bp.route('/status')
def monitor_status():
    """获取监控状态"""
    global stream_active, detector
    
    status = {
        "active": stream_active,
        "detector_initialized": detector is not None,
        "camera_available": camera is not None
    }
    
    return jsonify(status)

# WebSocket事件
@socketio.on('connect', namespace='/monitor')
def handle_connect():
    current_app.logger.info("客户端已连接到监控WebSocket")

@socketio.on('disconnect', namespace='/monitor')
def handle_disconnect():
    current_app.logger.info("客户端已断开监控WebSocket连接")

@socketio.on('request_frame', namespace='/monitor')
def handle_frame_request(data):
    """处理客户端请求帧的事件"""
    if not stream_active:
        emit('error', {"message": "监控未启动"})
        return
    
    # 帧请求会被generate_frames函数自动处理
    pass 