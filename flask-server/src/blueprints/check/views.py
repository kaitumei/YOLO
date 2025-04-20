# 前台检测功能相关接口

import base64,os
import csv
import io
import uuid
from datetime import datetime
import subprocess
import json
from collections import deque  
import threading
import re

import requests
from flask import Blueprint, render_template, jsonify, current_app, send_from_directory, make_response, Response, g, send_file
from flask import request
from flask import url_for
from flask_socketio import emit
from werkzeug.utils import secure_filename
from flask_wtf import FlaskForm

from config.prod import YoloBaseConfig
from config.prod import BaseConfig
from src.utils.decorators import login_required
from src.utils.exts import socketio
from aiortc import RTCPeerConnection, RTCSessionDescription

# 导入Redis客户端
import redis

# 导入stream蓝图中的视频元数据函数
from src.blueprints.stream.views import save_video_metadata, sync_videos_with_redis, REDIS_VIDEO_KEY_PREFIX, RECORD_FOLDER

# 导入本地的检测模块
from src.blueprints.check.detection import check_frame_for_accident, save_accident_image, ACCIDENT_CLASS_NAMES

UPLOAD_FOLDER = YoloBaseConfig.UPLOAD_FOLDER
RESULT_FOLDER = YoloBaseConfig.RESULT_FOLDER
YOLO_URL = YoloBaseConfig.URL

# 确保目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)
os.makedirs(RECORD_FOLDER, exist_ok=True)
print(f"[视频检测] 使用记录文件夹: {RECORD_FOLDER}")

bp = Blueprint('check', __name__, url_prefix='/check')

# Redis连接配置,#使用单独的数据库存储文件内容
redis_client = redis.Redis(
    host=BaseConfig.CACHE_REDIS_HOST,
    port=BaseConfig.CACHE_REDIS_PORT,
    password=BaseConfig.CACHE_REDIS_PASSWORD,
    db=1  
)

# 添加监控状，默认为关闭
monitoring_active = False

# 检测历史记录存储（本地缓存）
detection_history = deque(maxlen=10)  # 存储最近10条检测记录
detection_history_lock = threading.Lock()  # 添加锁保证线程安全

# 事故捕捉存储
accident_captures = deque(maxlen=20)  # 存储最近20条事故捕捉记录
accident_captures_lock = threading.Lock()  # 添加锁保证线程安全

# 添加视频质量和性能设置全局变量
video_quality_settings = {
    'quality': 'HIGH',
    'width': 1280,
    'height': 720,
    'jpegQuality': 0.9,
    'frameSkip': 3    # 添加跳帧率设置
}

# --------------------------------------------------------#
# ----------------------图片检测-已完成(已优化)-------------------#
# --------------------------------------------------------#
@bp.route("/picture" ,methods=['GET', 'POST'])
@login_required
def picture():
    if request.method == 'POST':
        file = request.files['image']
        image_data = file.read()
        
        # 获取原始文件名
        original_file_name = secure_filename(file.filename)

        # 保存原始图片到本地
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        original_filename = f"original_{timestamp}.jpg"
        processed_filename = f"processed_{timestamp}.jpg"

        # 确保目录存在
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(RESULT_FOLDER, exist_ok=True)
        
        # 保存原始图片到本地
        original_image_path = os.path.join(UPLOAD_FOLDER, original_filename)
        with open(original_image_path, 'wb') as f:
            f.write(image_data)

        print(f"[图片检测] 原始图片已保存: {original_image_path}")

        # 检查原始图片是否保存成功
        if not os.path.exists(original_image_path):
            print(f"[错误] 原始图片保存失败: {original_image_path}")
            return render_template('check/picture.html', error="图片保存失败，请重试")

        image_base64 = base64.b64encode(image_data).decode('utf-8')
        try:
            response = requests.post(YOLO_URL+'/img_predict', json={'image': image_base64}, timeout=30)
            response.raise_for_status()  # 如果响应状态码不是200，将引发HTTPError异常
            result = response.json()
            
            if 'error' in result:
                print(f"[错误] YOLO服务返回错误: {result['error']}")
                return render_template('check/picture.html', error=f"处理失败: {result['error']}")
                
            if 'result' not in result:
                print("[错误] YOLO服务返回的结果中没有图片数据")
                return render_template('check/picture.html', error="处理结果异常，请重试")
                
            result_image_data = base64.b64decode(result['result'])

            # 保存处理后的图片到本地 - 注意这里使用和URL相同的文件名
            processed_image_path = os.path.join(RESULT_FOLDER, processed_filename)
            with open(processed_image_path, 'wb') as f:
                f.write(result_image_data)
                
            print(f"[图片检测] 处理后图片已保存: {processed_image_path}")

            # 检查处理后的图片是否保存成功
            if not os.path.exists(processed_image_path):
                print(f"[错误] 处理后图片保存失败: {processed_image_path}")
                return render_template('check/picture.html', error="处理结果保存失败，请重试")

            # 修复BASE_DIR引用错误
            from config.prod import BASE_DIR
            
            try:
                # 解析出静态文件夹相对路径
                upload_rel_path = str(UPLOAD_FOLDER).replace(str(BASE_DIR), '').replace('\\', '/').lstrip('/')
                result_rel_path = str(RESULT_FOLDER).replace(str(BASE_DIR), '').replace('\\', '/').lstrip('/')
                
                print(f"[DEBUG] 上传文件夹相对路径: {upload_rel_path}")
                print(f"[DEBUG] 结果文件夹相对路径: {result_rel_path}")
                
                # 确认静态文件夹前缀 (static)
                static_prefix = 'static/'
                
                if upload_rel_path.startswith(static_prefix):
                    original_image_url = url_for('static', filename=f'{upload_rel_path[7:]}/{original_filename}')
                else:
                    # 如果路径不在static下，尝试直接用相对路径
                    original_image_url = f"/{upload_rel_path}/{original_filename}"
                    
                if result_rel_path.startswith(static_prefix):
                    processed_image_url = url_for('static', filename=f'{result_rel_path[7:]}/{processed_filename}')
                else:
                    # 如果路径不在static下，尝试直接用相对路径
                    processed_image_url = f"/{result_rel_path}/{processed_filename}"
            except Exception as e:
                # 如果路径处理出错，使用简单的备选URL生成方式
                print(f"[警告] 路径处理出错: {str(e)}, 使用简单URL")
                original_image_url = url_for('static', filename=f'uploads/{original_filename}')
                processed_image_url = url_for('static', filename=f'results/{processed_filename}')
            
            print(f"[图片检测] 原始图片URL: {original_image_url}")
            print(f"[图片检测] 处理后图片URL: {processed_image_url}")

            return render_template('check/picture.html',
                                result=result.get('detections', []),
                                original_image_url=original_image_url,
                                processed_image_url=processed_image_url,
                                original_image_name=original_file_name)
                                
        except requests.exceptions.RequestException as e:
            print(f"[错误] 连接YOLO服务失败: {str(e)}")
            return render_template('check/picture.html', error=f"连接处理服务失败: {str(e)}")
        except Exception as e:
            print(f"[错误] 处理图片时发生异常: {str(e)}")
            import traceback
            traceback.print_exc()
            return render_template('check/picture.html', error=f"处理图片时发生错误: {str(e)}")

    return render_template('check/picture.html')
# ----------------------------------------------------------------#
#----------------实时视频监控--已完成（已优化）---------------------#
# ----------------------------------------------------------------#
@bp.route('/monitor')
def monitor():
    # 添加参数访问历史记录
    return render_template('check/monitor.html', monitoring_active=monitoring_active)

@socketio.on('connect')
def handle_connect():
    print('Web客户端连接成功')
    # 发送当前监控状态给新连接的客户端
    emit('monitoring_status', {'active': monitoring_active})

# 添加切换监控状态的事件处理函数
@socketio.on('toggle_monitoring')
def handle_toggle_monitoring(data):
    global monitoring_active
    # 切换监控状态
    monitoring_active = data.get('active', False)
    # 广播新的监控状态给所有客户端
    socketio.emit('monitoring_status', {'active': monitoring_active})
    print(f'监控状态已切换为: {"开启" if monitoring_active else "关闭"}')
    return {'success': True, 'active': monitoring_active}

@socketio.on('detection_frame')
def handle_frame(data):
    """处理检测帧数据，只有当监控启用时才广播"""
    # 只有当监控处于开启状态时才广播帧数据
    global monitoring_active, video_quality_settings
    if monitoring_active:
        # 添加当前视频质量设置到数据中
        data['video_quality'] = video_quality_settings
        emit('update_frame', data, broadcast=True)
    else:
        # 只对发送者回复监控未开启的消息
        emit('monitoring_inactive', {'message': '监控当前处于关闭状态'})

@socketio.on('save_accident')
def handle_save_accident(data):
    """处理事故捕捉保存请求"""
    try:
        print("[事故捕捉] 收到事故捕捉请求", flush=True)
        
        # 基本验证
        if 'image' not in data:
            print("[事故捕捉] 错误: 图像数据缺失", flush=True)
            emit('accident_save_error', {'message': '图像数据缺失'})
            return
            
        if 'detections' not in data:
            print("[事故捕捉] 警告: 检测数据缺失，但仍继续处理", flush=True)
            # 不强制要求检测数据
        
        # 打印检测数据以便调试
        print(f"[事故捕捉] 检测数据: {data.get('detections')}", flush=True)
            
        # 创建事故记录对象
        accident_record = {
            'id': str(uuid.uuid4()),
            'timestamp': datetime.now().isoformat(),
            'image': data['image'],
            'detections': data.get('detections', []),
            'location': data.get('location', '未知位置'),
            'manually_triggered': True
        }
        
        print(f"[事故捕捉] 已创建记录ID: {accident_record['id']}", flush=True)
        
        # 保存到事故记录队列
        with accident_captures_lock:
            accident_captures.appendleft(accident_record)
            
        accident_count = len(accident_captures)
        print(f"[事故捕捉] 已保存事故记录，当前记录数: {accident_count}", flush=True)
        
        # 使用独立模块保存图像
        save_result = save_accident_image(data['image'])
        if save_result['success']:
            print(f"[事故捕捉] 事故图像已保存: {save_result['path']}", flush=True)
            accident_record['file_path'] = save_result['path']
            accident_record['file_url'] = save_result['url']
        else:
            print(f"[事故捕捉] 保存图像失败: {save_result.get('error')}", flush=True)
        
        # 返回保存成功的响应
        emit('accident_saved', {
            'status': 'success',
            'id': accident_record['id'],
            'message': '事故记录已保存'
        })
        
        print(f"[事故捕捉] 成功完成处理，返回事故ID: {accident_record['id']}", flush=True)
        
    except Exception as e:
        print(f"[事故捕捉] 保存事故记录失败: {str(e)}", flush=True)
        import traceback
        traceback.print_exc()
        emit('accident_save_error', {'message': f'保存失败: {str(e)}'})


# 截图功能
@socketio.on('capture')
def handle_capture(data):
    try:
        # 解码Base64图片数据
        image_data = base64.b64decode(data['image'])

        # 生成唯一文件名（时间戳格式）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.jpg"

        # 创建保存目录（如果不存在）
        os.makedirs(BaseConfig.SCREENSHOTS_DIR, exist_ok=True)

        # 保存图片文件
        save_path = os.path.join(BaseConfig.SCREENSHOTS_DIR, filename)
        with open(save_path, 'wb') as f:
            f.write(image_data)

        # 返回成功响应
        emit('capture_success', {
            'message': '截图保存成功',
            'filename': filename,
            'filepath': f"/static/screenshots/{filename}"
        })
        print(f"[截图成功] 保存路径：{save_path}")

    except Exception as e:
        print(f"[截图错误] {str(e)}")
        emit('capture_error', {'message': '服务器保存失败'})

# 视频保存
@socketio.on('save_video')
def handle_save_video(data):
    try:
        print("[视频保存] 开始处理接收的视频数据")
        
        # 基本验证
        if 'video' not in data:
            emit('video_save_error', {'message': '视频数据缺失'})
            return
        
        # 尝试解码Base64数据
        try:
            video_data = base64.b64decode(data['video'])
            print(f"[视频保存] 解码成功，数据大小: {len(video_data)/1024/1024:.2f} MB")
        except Exception as e:
            print(f"[视频保存错误] Base64解码失败: {str(e)}")
            emit('video_save_error', {'message': f'数据解码失败: {str(e)}'})
            return
        
        # 文件大小检查
        file_size = len(video_data)
        if file_size == 0:
            emit('video_save_error', {'message': '接收到空文件'})
            return
        
        # 确保目录存在
        os.makedirs(BaseConfig.VIDEO_SAVE_DIR, exist_ok=True)
        
        # 创建唯一文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recording_{timestamp}.webm"
        save_path = os.path.join(BaseConfig.VIDEO_SAVE_DIR, filename)
        
        print(f"[视频保存] 开始写入文件: {save_path}")
        
        # 写入文件
        with open(save_path, 'wb') as f:
            f.write(video_data)
        
        print(f"[视频保存] 文件写入完成，大小: {os.path.getsize(save_path)/1024/1024:.2f} MB")
        
        # 验证文件是否成功保存
        if not os.path.exists(save_path):
            emit('video_save_error', {'message': '文件写入失败'})
            return
        
        # 返回成功结果
        emit('video_saved', {
            'message': '视频保存成功',
            'filename': filename,
            'filepath': f"/videos/{filename}",
            'size': file_size
        })
        
        print(f"[视频保存] 成功处理视频: {filename}")
        
    except Exception as e:
        print(f"[视频保存错误] 异常: {str(e)}")
        import traceback
        traceback.print_exc()
        emit('video_save_error', {'message': f'服务器处理错误: {str(e)}'})

# 下载视频
@bp.route('/videos/<filename>')
@login_required
def download_video(filename):
    """下载视频（同时支持原始和处理后的视频）"""
    try:
        filename = secure_filename(filename)
        
        # 首先尝试从处理结果文件夹获取
        file_path = os.path.join(RESULT_FOLDER, filename)
        if os.path.exists(file_path):
            return send_from_directory(
                directory=RESULT_FOLDER, 
                path=filename,
                as_attachment=True,
                download_name=filename
            )
            
        # 如果不存在，尝试从原始视频文件夹获取
        file_path = os.path.join(BaseConfig.VIDEO_SAVE_DIR, filename)
        if os.path.exists(file_path):
            return send_from_directory(
                directory=BaseConfig.VIDEO_SAVE_DIR, 
                path=filename,
                as_attachment=True,
                download_name=filename
            )
            
        return jsonify({"error": "文件不存在"}), 404
    except Exception as e:
        print(f"[视频下载错误] {str(e)}")
        return jsonify({"error": f"下载失败: {str(e)}"}), 500

@bp.route('/api/video/upload', methods=['POST'])
@login_required
def upload_video():
    try:
        if 'video' not in request.files:
            return jsonify({"error": "未提供视频文件"}), 400
            
        file = request.files['video']
        if file.filename == '':
            return jsonify({"error": "文件名为空"}), 400
            
        # 检查文件类型
        filename = file.filename.lower()
        if not filename.endswith(('.webm', '.mp4', '.avi', '.mov')):
            return jsonify({"error": "不支持的文件类型，仅支持webm、mp4、avi和mov格式"}), 400
            
        # 检查文件大小
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        max_size = 200 * 1024 * 1024  # 200MB
        if file_size > max_size:
            return jsonify({"error": f"文件过大，最大限制为200MB，当前大小为{file_size/1024/1024:.2f}MB"}), 413
        
        # 创建保存目录
        try:
            os.makedirs(BaseConfig.VIDEO_SAVE_DIR, exist_ok=True)
        except Exception as e:
            return jsonify({"error": f"创建目录失败: {str(e)}"}), 500
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        secure_name = secure_filename(file.filename)
        _, ext = os.path.splitext(secure_name)
        new_filename = f"recording_{timestamp}{ext}"
        
        # 保存文件
        save_path = os.path.join(BaseConfig.VIDEO_SAVE_DIR, new_filename)
        file.save(save_path)
        
        # 检查文件完整性
        if not os.path.exists(save_path) or os.path.getsize(save_path) == 0:
            try:
                os.remove(save_path)  # 删除可能损坏的文件
            except:
                pass
            return jsonify({"error": "文件保存失败或文件为空"}), 500
        
        # 可选: 生成缩略图
        thumbnail_path = None
        try:
            import cv2
            thumbnail_dir = os.path.join(BaseConfig.VIDEO_SAVE_DIR, 'thumbnails')
            os.makedirs(thumbnail_dir, exist_ok=True)
            thumbnail_path = os.path.join(thumbnail_dir, f"thumb_{new_filename.replace(ext, '.jpg')}")
            
            cap = cv2.VideoCapture(save_path)
            cap.set(cv2.CAP_PROP_POS_FRAMES, 30)  # 获取第30帧作为缩略图
            success, image = cap.read()
            if success:
                image = cv2.resize(image, (320, 180))
                cv2.imwrite(thumbnail_path, image)
            cap.release()
        except Exception as e:
            print(f"[缩略图生成失败] {str(e)}")
            # 不影响主流程，继续执行
        
        return jsonify({
            "status": "success",
            "message": "视频保存成功",
            "filename": new_filename,
            "filepath": f"/videos/{new_filename}",
            "size": file_size,
            "thumbnail": thumbnail_path is not None,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        print(f"[视频上传错误] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@bp.route('/video_predict', methods=['POST'])
@login_required
def video_predict():
    """处理视频检测请求"""
    print("[DEBUG] 视频检测API被调用")
    try:
        print("[DEBUG] 请求方法:", request.method)
        print("[DEBUG] 请求头:", dict(request.headers))
        
        if 'video' not in request.files:
            print("[DEBUG] 没有找到视频文件")
            return jsonify({"error": "未提供视频文件"}), 400
            
        file = request.files['video']
        if file.filename == '':
            print("[DEBUG] 文件名为空")
            return jsonify({"error": "文件名为空"}), 400
            
        # 检查文件类型
        filename = file.filename.lower()
        print(f"[DEBUG] 文件名: {filename}")
        if not filename.endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
            print("[DEBUG] 不支持的文件类型")
            return jsonify({"error": "不支持的文件类型，仅支持mp4、avi、mov、mkv和webm格式"}), 400
            
        # 读取视频内容
        video_data = file.read()
        
        # 保存上传的视频文件到Redis
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        secure_name = secure_filename(file.filename)
        _, ext = os.path.splitext(secure_name)
        input_filename = f"input_{timestamp}{ext}"
        
        # 获取唯一ID用于文件命名
        file_uuid = str(uuid.uuid4())[:8]
        record_filename = f"record_{timestamp}_{file_uuid}{ext}"
        
        # 确保目录存在
        try:
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            os.makedirs(RESULT_FOLDER, exist_ok=True)
            os.makedirs(RECORD_FOLDER, exist_ok=True)
            print(f"[视频检测] 确保目录存在: UPLOAD_FOLDER={UPLOAD_FOLDER}, RESULT_FOLDER={RESULT_FOLDER}, RECORD_FOLDER={RECORD_FOLDER}")
        except Exception as e:
            print(f"[视频检测] 创建目录失败: {str(e)}")
            return jsonify({"error": f"创建保存目录失败: {str(e)}"}), 500
        
        # 同时保存到本地文件系统作为备份
        input_path = os.path.join(UPLOAD_FOLDER, input_filename)
        with open(input_path, 'wb') as f:
            f.write(video_data)
        
        print(f"[视频检测] 原始文件已保存: 本地={input_path}")
        
        # 检查文件是否保存成功
        if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
            print(f"[视频检测] 原始文件保存失败或为空")
            return jsonify({"error": "原始视频文件保存失败或为空"}), 500
        
        # 发送请求到YOLO服务器进行处理
        try:
            # 使用with语句正确关闭文件
            with open(input_path, 'rb') as video_file:
                files = {'video': (input_filename, video_file, 'video/mp4')}
                print(f"[视频检测] 发送请求到YOLO服务器: {YOLO_URL}/video_predict")
                response = requests.post(YOLO_URL + '/video_predict', files=files, timeout=300)  # 增加超时时间
        except Exception as e:
            print(f"[视频检测] 发送请求失败: {str(e)}")
            return jsonify({"error": f"连接YOLO服务器失败: {str(e)}"}), 500
        
        # 检查响应状态
        if response.status_code != 200:
            print(f"[视频检测] YOLO服务器返回错误: {response.status_code}, 内容: {response.text}")
            return jsonify({"error": f"YOLO服务器处理失败: {response.text}"}), 500
            
        result = response.json()
        print(f"[视频检测] YOLO处理结果: {result}")
        
        # 存储检测结果
        detection_results = []
        
        # 通过socketio广播检测结果给所有连接的客户端
        if 'detections' in result:
            try:
                detections = result['detections']
                # 添加更详细的日志记录，用于调试
                detection_count = 0
                frame_count = 0
                
                # 打印整个检测结果以便调试
                print(f"[视频检测] 原始检测结果数据: {detections}")
                
                if isinstance(detections, list):
                    frame_count = len(detections)
                    for det in detections:
                        if isinstance(det, dict) and 'detections' in det:
                            detection_count += len(det['detections'])
                            # 检查检测对象的结构
                            if det['detections'] and len(det['detections']) > 0:
                                first_obj = det['detections'][0]
                                print(f"[视频检测] 检测对象结构: {first_obj}")
                                print(f"[视频检测] 检测对象字段: {list(first_obj.keys())}")
                
                print(f"[视频检测] 发送检测结果到前端: {frame_count} 帧数据，共 {detection_count} 个检测对象")
                
                # 记录检测结果的结构，帮助调试
                if len(detections) > 0:
                    sample = detections[0]
                    print(f"[视频检测] 检测结果样本结构: {type(sample)}")
                    if isinstance(sample, dict):
                        print(f"[视频检测] 检测结果字段: {list(sample.keys())}")
                        if 'detections' in sample and len(sample['detections']) > 0:
                            print(f"[视频检测] 检测对象样本: {sample['detections'][0]}")
                
                # 将结果通过socketio发送给前端
                socketio.emit('update_frame', {
                    'detections': detections,
                    'detection_type': result.get('detection_type', 'general'),
                    'image': ''  # 添加空图像字段以兼容前端代码
                })
                
                # 保存检测结果以用于元数据
                detection_results = detections
                
                print(f"[视频检测] 检测结果已发送到前端")
            except Exception as e:
                print(f"[视频检测] 发送检测结果失败: {str(e)}")
                import traceback
                traceback.print_exc()
        
        # 下载处理后的视频
        download_url = result.get('download_url', '')
        video_duration = result.get('duration', '00:00:00')
        
        if download_url:
            output_filename = os.path.basename(download_url)
            try:
                # 检查URL格式，确保正确处理相对和绝对URL
                if not download_url.startswith(('http://', 'https://')):
                    full_url = YOLO_URL + download_url
                else:
                    full_url = download_url
                    
                print(f"[视频检测] 下载处理后的视频: {full_url}")
                download_response = requests.get(full_url, timeout=180)  # 增加超时时间
                
                if download_response.status_code == 200:
                    # 获取处理后的视频数据
                    processed_video_data = download_response.content
                    
                    if len(processed_video_data) == 0:
                        print("[视频检测] 警告：下载的视频数据为空")
                        return jsonify({"error": "下载的处理视频为空"}), 500
                    
                    # 保存到RESULT_FOLDER目录
                    output_path = os.path.join(RESULT_FOLDER, output_filename)
                    with open(output_path, 'wb') as f:
                        f.write(processed_video_data)
                    
                    # 检查文件是否保存成功
                    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                        print(f"[视频检测] 处理后视频保存失败或为空: {output_path}")
                    else:
                        print(f"[视频检测] 处理后视频已保存到RESULT_FOLDER: {output_path}")
                    
                    # 同时保存到media/record目录
                    record_path = os.path.join(RECORD_FOLDER, record_filename)
                    with open(record_path, 'wb') as f:
                        f.write(processed_video_data)
                    
                    # 检查文件是否保存成功
                    if not os.path.exists(record_path) or os.path.getsize(record_path) == 0:
                        print(f"[视频检测] 处理后视频保存到RECORD_FOLDER失败或为空: {record_path}")
                    else:
                        print(f"[视频检测] 处理后视频已保存到RECORD_FOLDER: {record_path}")
                    
                    # 生成视频缩略图
                    thumbnail_filename = f"thumb_{record_filename.replace('.mp4', '.jpg').replace('.webm', '.jpg')}"
                    thumbnail_path = os.path.join(RECORD_FOLDER, 'thumbnails', thumbnail_filename)
                    
                    # 确保缩略图目录存在
                    os.makedirs(os.path.join(RECORD_FOLDER, 'thumbnails'), exist_ok=True)
                    
                    try:
                        import cv2
                        # 使用OpenCV生成缩略图
                        video = cv2.VideoCapture(record_path)
                        # 尝试跳转到1秒处的帧
                        video.set(cv2.CAP_PROP_POS_MSEC, 1000)
                        success, image = video.read()
                        if success:
                            # 缩放到合适大小
                            height, width = image.shape[:2]
                            max_height = 180
                            if height > max_height:
                                scale = max_height / height
                                new_width = int(width * scale)
                                image = cv2.resize(image, (new_width, max_height))
                            # 保存缩略图
                            cv2.imwrite(thumbnail_path, image)
                            print(f"[视频检测] 生成缩略图成功: {thumbnail_path}")
                        else:
                            print(f"[视频检测] 无法读取视频帧生成缩略图")
                        video.release()
                    except Exception as e:
                        print(f"[视频检测] 生成缩略图失败: {str(e)}")
                        
                    # 更新结果URL为本地URL
                    result['download_url'] = url_for('check.download_video', filename=output_filename)
                    # 同时设置stream_url来支持视频播放 - 使用流式播放路由
                    result['stream_url'] = url_for('check.stream_video', filename=output_filename)
                    # 添加record路径信息到结果
                    result['record_path'] = os.path.join('media', 'record', record_filename)
                    result['record_filename'] = record_filename
                    result['thumbnail_path'] = os.path.join('media', 'record', 'thumbnails', thumbnail_filename) if os.path.exists(thumbnail_path) else ''
                    
                    # 保存视频元数据到Redis
                    try:
                        # 获取视频时长
                        if not video_duration or video_duration == '00:00:00':
                            try:
                                # 尝试使用ffprobe获取视频时长
                                cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{record_path}"'
                                result_duration = subprocess.check_output(cmd, shell=True, text=True).strip()
                                seconds = float(result_duration)
                                hours = int(seconds // 3600)
                                minutes = int((seconds % 3600) // 60)
                                secs = int(seconds % 60)
                                video_duration = f"{hours:02d}:{minutes:02d}:{secs:02d}"
                            except Exception as e:
                                print(f"[视频检测] 获取视频时长失败: {str(e)}")
                        
                        # 获取检测结果统计
                        detection_stats = {}
                        total_objects = 0
                        if detection_results:
                            for frame in detection_results:
                                if isinstance(frame, dict) and 'detections' in frame:
                                    frame_detections = frame['detections']
                                    for detection in frame_detections:
                                        obj_class = detection.get('class', 'unknown')
                                        if obj_class not in detection_stats:
                                            detection_stats[obj_class] = 0
                                        detection_stats[obj_class] += 1
                                        total_objects += 1
                                        
                        # 创建视频元数据对象
                        video_metadata = {
                            'filename': record_filename,
                            'path': record_path,
                            'url': f"/media/record/{record_filename}",
                            'thumbnail_url': f"/media/record/thumbnails/{thumbnail_filename}" if os.path.exists(thumbnail_path) else '',
                            'size': f"{os.path.getsize(record_path) / (1024 * 1024):.2f}MB",
                            'created': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'timestamp': timestamp,
                            'duration': video_duration,
                            'detection_results': detection_stats,
                            'total_detections': total_objects,
                            'tags': ['检测'],
                            'is_processed': True,
                            'original_filename': secure_name
                        }
                        
                        # 保存元数据到Redis
                        save_result = save_video_metadata(video_metadata)
                        if save_result.get('success', False):
                            result['video_id'] = save_result.get('video_id')
                            print(f"[视频检测] 视频元数据已保存到Redis，ID: {save_result.get('video_id')}")
                        else:
                            print(f"[视频检测] 保存视频元数据失败: {save_result.get('error')}")
                    except Exception as e:
                        print(f"[视频检测] 保存视频元数据到Redis出错: {str(e)}")
                        import traceback
                        traceback.print_exc()
                    
                    print(f"[视频检测] 处理完成，更新的下载URL: {result['download_url']}")
                    
                    # 发送处理完成通知
                    socketio.emit('video_process_complete', {
                        'status': '视频处理完成',
                        'download_url': result['download_url'],
                        'filename': output_filename,
                        'video_id': result.get('video_id', '')
                    })
                else:
                    print(f"[视频检测] 下载视频失败，状态码: {download_response.status_code}, 内容: {download_response.text[:200]}")
                    return jsonify({"error": f"下载处理后的视频失败: HTTP {download_response.status_code}"}), 500
            except Exception as e:
                print(f"[视频检测] 下载或保存视频失败: {str(e)}")
                import traceback
                traceback.print_exc()
                return jsonify({"error": f"下载或保存处理后的视频失败: {str(e)}"}), 500
        else:
            print("[视频检测] YOLO结果中没有下载URL")
            return jsonify({"error": "YOLO处理结果中缺少视频下载链接"}), 500
        
        # 同步更新视频库
        try:
            sync_videos_with_redis()
        except Exception as e:
            print(f"[视频检测] 同步视频库失败: {str(e)}")
        
        return jsonify(result)
        
    except Exception as e:
        print(f"[视频检测错误] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# 视频检测页面 
@bp.route('/video')
@login_required
def video():
    """视频检测页面"""
    return render_template('check/video.html')

#-----------------------------------------------------------------#
# ----------------------------系统状态-----------------------------#
#-----------------------------------------------------------------#
@bp.route('/healthcheck')
def healthcheck():
    """健康检查接口"""
    return jsonify({
        'status': 'healthy',
        'time': datetime.now().isoformat()
    })


@bp.route('/api/detection_history', methods=['GET'])
@login_required
def get_detection_history():
    """获取检测历史记录"""
    try:
        # 尝试从YOLO服务获取最新的检测历史
        try:
            response = requests.get(f"{YOLO_URL}/api/detection_history", timeout=5)
            if response.status_code == 200:
                history_data = response.json()
                # 更新本地缓存
                with detection_history_lock:
                    detection_history.clear()
                    for item in history_data:
                        detection_history.append(item)
                # print(f"[检测历史] 从YOLO服务获取了{len(history_data)}条历史记录")
        except Exception as e:
            # print(f"[检测历史] 从YOLO服务获取历史记录失败: {str(e)}")
            # 出错时使用本地缓存的记录
            pass
        
        # 返回本地缓存的记录
        with detection_history_lock:
            history_list = list(detection_history)
        
        return jsonify({
            'status': 'success',
            'count': len(history_list),
            'history': history_list
        })
    except Exception as e:
        # print(f"[检测历史] 获取历史记录出错: {str(e)}")
        pass
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/api/accident_captures', methods=['GET'])
@login_required
def get_accident_captures():
    """获取事故捕捉记录"""
    try:
        with accident_captures_lock:
            captures_list = list(accident_captures)
        
        # 处理返回数据，可能需要限制图像大小
        for capture in captures_list:
            # 限制图像大小以减少响应大小
            if 'image' in capture and capture['image']:
                # 仅当请求参数中指定了include_images=true时才包含图像数据
                if request.args.get('include_images') != 'true':
                    capture['image'] = ''
        
        return jsonify({
            'status': 'success',
            'count': len(captures_list),
            'captures': captures_list
        })
    except Exception as e:
        print(f"[事故捕捉] 获取事故记录失败: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# 添加清空事故记录的API
@bp.route('/api/accident_captures/clear', methods=['POST'])
@login_required
def clear_accident_captures():
    """清空事故捕捉记录"""
    try:
        with accident_captures_lock:
            accident_captures.clear()
        
        return jsonify({
            'status': 'success',
            'message': '所有事故记录已清空'
        })
    except Exception as e:
        print(f"[事故捕捉] 清空事故记录失败: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# 添加一个额外的Socket事件处理函数，用于处理检测结果并自动检查事故
@socketio.on('update_detections')
def detection_handler(data):
    """处理并存储检测结果，自动检查事故"""
    try:
        # 如果监控未启用，直接返回
        global monitoring_active
        if not monitoring_active:
            return
            
        # 打印检测数据以便调试
        print(f"[检测处理] 收到检测数据: {data.get('detections')}", flush=True)
        
        # 同时保存到历史记录中
        if 'detections' in data and data['detections']:
            with detection_history_lock:
                # 创建新的记录对象
                record = {
                    'timestamp': datetime.now().isoformat(),
                    'detections': data['detections'],
                    'image': data.get('image', '')[:100000] if data.get('image') else None  # 限制图像大小
                }
                detection_history.appendleft(record)
                print(f"[检测历史] 已保存新的检测记录，当前历史记录数: {len(detection_history)}", flush=True)
                
                # 检查是否有事故，如果有则自动保存到事故记录中
                if 'image' in data and data.get('image') and check_frame_for_accident(data['detections']):
                    print("[检测历史] 发现事故，自动保存到事故记录", flush=True)
                    
                    # 创建事故记录
                    accident_record = {
                        'id': str(uuid.uuid4()),
                        'timestamp': datetime.now().isoformat(),
                        'image': data['image'],
                        'detections': data['detections'],
                        'location': data.get('location', '未知位置'),
                        'auto_detected': True
                    }
                    
                    # 保存到事故队列
                    with accident_captures_lock:
                        accident_captures.appendleft(accident_record)
                        print(f"[事故检测] 自动添加到事故队列，当前记录数: {len(accident_captures)}", flush=True)
                    
                    # 保存图像到文件系统
                    save_result = save_accident_image(data['image'])
                    if save_result['success']:
                        print(f"[事故检测] 自动保存事故图像成功: {save_result['path']}", flush=True)
                        accident_record['file_path'] = save_result['path']
                        accident_record['file_url'] = save_result['url']
                    
                    # 通知客户端有事故捕捉
                    socketio.emit('accident_detected', {
                        'id': accident_record['id'],
                        'timestamp': accident_record['timestamp'],
                        'message': '系统自动检测到事故车辆',
                        'success': True
                    })
                    
                    # 发送短信通知 (新增)
                    try:
                        from src.utils.sms import send_accident_notification
                        
                        # 检查是否启用了短信功能
                        sms_enabled = current_app.config.get('SMS_ENABLED', False)
                        if not sms_enabled:
                            print("[事故通知] 短信功能未启用，跳过短信通知", flush=True)
                            return
                            
                        # 获取配置中的通知手机号码
                        notify_numbers = current_app.config.get('ACCIDENT_NOTIFY_NUMBERS', [])
                        if notify_numbers:
                            # 格式化时间为人类可读形式
                            accident_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            # 获取事故类型
                            accident_type = "交通事故"
                            # 获取位置信息
                            location = accident_record.get('location', '监控区域')
                            
                            # 遍历所有需要通知的手机号码
                            for mobile in notify_numbers:
                                try:
                                    # 发送短信通知
                                    result = send_accident_notification(mobile, accident_type, location, accident_time)
                                    if result:
                                        print(f"[事故通知] 成功发送短信通知到 {mobile}", flush=True)
                                    else:
                                        print(f"[事故通知] 发送短信通知到 {mobile} 失败", flush=True)
                                except Exception as sms_err:
                                    print(f"[事故通知] 向 {mobile} 发送短信时出错: {str(sms_err)}", flush=True)
                        else:
                            print("[事故通知] 未配置通知手机号码，跳过短信通知", flush=True)
                    except Exception as notify_err:
                        print(f"[事故通知] 发送短信通知时出错: {str(notify_err)}", flush=True)
                    
    except Exception as e:
        print(f"[检测处理] 处理检测结果失败: {str(e)}", flush=True)
        import traceback
        traceback.print_exc()

# 添加处理视频质量设置的事件
@socketio.on('set_video_quality')
def handle_set_video_quality(data):
    """处理视频质量设置变更"""
    global video_quality_settings
    
    try:
        # 更新全局视频质量设置
        video_quality_settings = {
            'quality': data.get('quality', 'HIGH'),
            'width': data.get('width', 1280),
            'height': data.get('height', 720),
            'jpegQuality': data.get('jpegQuality', 0.9),
            'frameSkip': data.get('frameSkip', video_quality_settings.get('frameSkip', 3))  # 保留现有的跳帧率或使用默认值
        }
        
        print(f"[视频设置] 画质已更新为: {video_quality_settings['quality']}, " \
              f"分辨率: {video_quality_settings['width']}x{video_quality_settings['height']}, " \
              f"JPEG质量: {video_quality_settings['jpegQuality']}, " \
              f"跳帧率: {video_quality_settings['frameSkip']}")
        
        # 广播视频质量更新消息给所有客户端
        socketio.emit('video_quality_updated', video_quality_settings)
        
        # 返回成功响应
        return {'success': True, 'message': '视频质量设置已更新'}
    except Exception as e:
        print(f"[视频设置] 更新画质设置失败: {str(e)}")
        return {'success': False, 'message': f'更新画质设置失败: {str(e)}'}

@bp.route('/stream/<filename>')
@login_required
def stream_video(filename):
    """流式播放视频文件（提供视频流而不是下载）"""
    try:
        filename = secure_filename(filename)
        
        # 首先尝试从处理结果文件夹获取
        file_path = os.path.join(RESULT_FOLDER, filename)
        if not os.path.exists(file_path):
            # 如果不存在，尝试从原始视频文件夹获取
            file_path = os.path.join(BaseConfig.VIDEO_SAVE_DIR, filename)
            if not os.path.exists(file_path):
                return jsonify({"error": "文件不存在"}), 404
        
        # 获取文件大小
        file_size = os.path.getsize(file_path)
        
        # 处理范围请求
        range_header = request.headers.get('Range', None)
        byte1, byte2 = 0, None
        
        if range_header:
            match = re.search(r'bytes=(\d+)-(\d*)', range_header)
            if match:
                groups = match.groups()
                byte1 = int(groups[0]) if groups[0] else 0
                byte2 = int(groups[1]) if groups[1] else file_size - 1
        
        # 增加分块大小（4MB），提高流媒体传输效率
        chunk_size = 4 * 1024 * 1024
        if not byte2:
            byte2 = min(byte1 + chunk_size, file_size - 1)
        
        # 计算实际需要读取的长度
        length = byte2 - byte1 + 1
        
        # 创建响应
        def generate():
            with open(file_path, 'rb') as f:
                f.seek(byte1)
                data = f.read(length)
                yield data

        # 确定MIME类型
        mime_type = 'video/mp4'
        if filename.endswith('.webm'):
            mime_type = 'video/webm'
        elif filename.endswith('.avi'):
            mime_type = 'video/x-msvideo'
        elif filename.endswith('.mov'):
            mime_type = 'video/quicktime'
        
        response = Response(
            generate(),
            206,  # Partial Content
            mimetype=mime_type,
            direct_passthrough=True
        )
        
        # 设置响应头，优化流媒体传输
        response.headers.add('Content-Range', f'bytes {byte1}-{byte2}/{file_size}')
        response.headers.add('Accept-Ranges', 'bytes')
        response.headers.add('Content-Length', str(length))
        # 优化缓存设置，允许浏览器对视频进行充分缓冲
        response.headers.add('Cache-Control', 'public, max-age=3600')
        # 添加额外的优化头
        response.headers.add('X-Content-Type-Options', 'nosniff')
        response.headers.add('Connection', 'keep-alive')
        # 设置视频内容处理
        response.headers.add('Content-Disposition', f'inline; filename="{filename}"')
        # 添加允许的跨域请求头
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Range, Accept-Ranges, Content-Type')
        
        return response
    except Exception as e:
        print(f"[视频流播放错误] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"流式播放失败: {str(e)}"}), 500

