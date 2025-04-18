from flask import render_template, request, jsonify, current_app
from flask_socketio import emit

from src.utils.decorators import login_required
from . import bp
from src.utils.stream_utils import stream_manager
from src.utils.exts import socketio
import os
from datetime import datetime
from werkzeug.utils import secure_filename

# 设置记录文件夹
RECORD_FOLDER = os.path.join(os.path.dirname(__file__), 'record')


@bp.route('/')
def index():
    """流媒体首页"""
    return render_template('stream/index.html')

@bp.route('/streams')
def streams():
    """流媒体列表页"""
    active_streams = stream_manager.get_active_streams()
    return render_template('stream/streams.html', active_streams=active_streams)
    return render_template('stream/webcam.html')

@bp.route('/rtmp-push')
def rtmp_push():
    """RTMP推流页面"""
    rtmp_server = "rtmp://127.0.0.1/live/livestream"
    return render_template('stream/rtmp_push.html', rtmp_server=rtmp_server)

@bp.route('/api/push-ipcam', methods=['POST'])
def push_ipcam():
    """API: 推送IP摄像头到SRS流媒体服务器"""
    data = request.get_json()
    
    if not data or 'camera_url' not in data:
        return jsonify({"success": False, "message": "需要提供摄像头URL"}), 400
        
    camera_url = data['camera_url']
    rtmp_server = "rtmp://127.0.0.1/live/livestream"
    
    # 从请求中获取视频参数
    video_params = {
        'video_codec': data.get('video_codec', 'copy'),
        'video_bitrate': data.get('video_bitrate'),
        'video_size': data.get('video_size'),
        'video_framerate': data.get('video_framerate'),
        'audio_codec': data.get('audio_codec', 'aac'),
        'audio_bitrate': data.get('audio_bitrate'),
        'audio_sample_rate': data.get('audio_sample_rate', '44100'),
        'audio_channels': data.get('audio_channels', '1'),
    }
    
    # 使用StreamManager将IP摄像头流推送到SRS服务器
    result = stream_manager.push_ipcam_to_srs(camera_url, rtmp_server, video_params=video_params)
    
    if result['success']:
        return jsonify({
            "success": True,
            "message": result['message'],
            "rtmp_server": rtmp_server,
            "stream_id": result.get('stream_id'),
            "video_params": result.get('video_params', {})
        })
    else:
        return jsonify({
            "success": False,
            "message": result['message']
        }), 500

@bp.route('/api/stop-push', methods=['POST'])
def stop_push():
    """API: 停止RTMP推流"""
    data = request.get_json()
    
    if not data or 'stream_id' not in data:
        return jsonify({"success": False, "message": "需要提供流ID"}), 400
        
    stream_id = data['stream_id']
    
    # 使用StreamManager停止推流
    result = stream_manager.stop_push(stream_id)
    
    return jsonify(result)

@bp.route('/api/active-streams', methods=['GET'])
def active_streams():
    """API: 获取所有活动的推流任务"""
    streams = stream_manager.get_active_streams()
    return jsonify({
        "success": True,
        "streams": streams
    })

# WebSocket事件处理
@socketio.on('stream_request')
def handle_stream_request(data):
    """处理流媒体状态请求"""
    streams = stream_manager.get_active_streams()
    emit('stream_update', {
        'type': 'stream_status',
        'streams': streams
    }) 

#-----------------------------监控回放功能-------------------------#
# --------------------------------------------------------#

@bp.route('/playback')
@login_required
def playback():
    """监控回放页面"""
    
    # 获取记录文件夹中的所有视频文件
    video_files = []
    try:
        if os.path.exists(RECORD_FOLDER):
            # 列出所有视频文件
            for file in os.listdir(RECORD_FOLDER):
                if file.lower().endswith(('.mp4', '.webm', '.avi', '.mov', '.mkv')):
                    full_path = os.path.join(RECORD_FOLDER, file)
                    # 获取文件信息
                    stat_info = os.stat(full_path)
                    size_mb = stat_info.st_size / (1024 * 1024)
                    create_time = datetime.fromtimestamp(stat_info.st_ctime)
                    
                    # 尝试提取时间戳信息
                    timestamp_str = ""
                    if "record_" in file and "_" in file:
                        try:
                            date_part = file.split("record_")[1].split("_")[0]
                            if len(date_part) == 14:  # 格式为YYYYMMDDHHmmSS
                                timestamp_str = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]} {date_part[8:10]}:{date_part[10:12]}:{date_part[12:14]}"
                        except:
                            pass
                    
                    video_files.append({
                        'filename': file,
                        'path': f"/media/record/{file}",
                        'size': f"{size_mb:.2f}MB",
                        'created': create_time.strftime("%Y-%m-%d %H:%M:%S"),
                        'timestamp': timestamp_str or create_time.strftime("%Y-%m-%d %H:%M:%S")
                    })
            
            # 按创建时间倒序排序
            video_files.sort(key=lambda x: x['created'], reverse=True)
    except Exception as e:
        print(f"[监控回放] 获取视频列表出错: {str(e)}")
    
    return render_template('stream/playback.html', video_files=video_files)

@bp.route('/api/playback/videos')
@login_required
def get_playback_videos():
    """API: 获取所有可回放的视频列表"""
    try:
        video_files = []
        if os.path.exists(RECORD_FOLDER):
            for file in os.listdir(RECORD_FOLDER):
                if file.lower().endswith(('.mp4', '.webm', '.avi', '.mov', '.mkv')):
                    full_path = os.path.join(RECORD_FOLDER, file)
                    stat_info = os.stat(full_path)
                    size_mb = stat_info.st_size / (1024 * 1024)
                    create_time = datetime.fromtimestamp(stat_info.st_ctime)
                    
                    # 时间戳提取
                    timestamp_str = ""
                    if "record_" in file and "_" in file:
                        try:
                            date_part = file.split("record_")[1].split("_")[0]
                            if len(date_part) == 14:
                                timestamp_str = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]} {date_part[8:10]}:{date_part[10:12]}:{date_part[12:14]}"
                        except:
                            pass
                    
                    video_files.append({
                        'filename': file,
                        'url': f"/media/record/{file}",
                        'size': f"{size_mb:.2f}MB",
                        'created': create_time.strftime("%Y-%m-%d %H:%M:%S"),
                        'timestamp': timestamp_str or create_time.strftime("%Y-%m-%d %H:%M:%S")
                    })
            
            # 按创建时间倒序排序
            video_files.sort(key=lambda x: x['created'], reverse=True)
        
        return jsonify({
            'status': 'success',
            'data': video_files
        })
    except Exception as e:
        print(f"[监控回放API] 获取视频列表出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"获取视频列表失败: {str(e)}"
        }), 500

@bp.route('/api/playback/delete/<filename>', methods=['DELETE'])
@login_required
def delete_playback_video(filename):
    """API: 删除回放视频"""
    try:
        filename = secure_filename(filename)
        file_path = os.path.join(RECORD_FOLDER, filename)
        
        if not os.path.exists(file_path):
            return jsonify({
                'status': 'error',
                'message': '文件不存在'
            }), 404
            
        os.remove(file_path)
        return jsonify({
            'status': 'success',
            'message': '文件删除成功'
        })
    except Exception as e:
        print(f"[监控回放API] 删除视频失败: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"删除视频失败: {str(e)}"
        }), 500