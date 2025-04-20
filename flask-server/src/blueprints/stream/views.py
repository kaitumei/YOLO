from flask import render_template, request, jsonify, current_app, send_from_directory
from flask_socketio import emit

from src.utils.decorators import login_required
from . import bp
from src.utils.stream_utils import stream_manager
from src.utils.exts import socketio
import os
import json
from datetime import datetime
from werkzeug.utils import secure_filename
from config.prod import BaseConfig

# 导入Redis客户端
import redis

# 设置记录文件夹 - 修正为统一使用BaseConfig中的路径
RECORD_FOLDER = os.path.join(BaseConfig.MEDIA_ROOT, 'record')
print(f"[监控回放] 使用记录文件夹: {RECORD_FOLDER}")

# Redis连接配置
redis_client = redis.Redis(
    host=BaseConfig.CACHE_REDIS_HOST,
    port=BaseConfig.CACHE_REDIS_PORT,
    password=BaseConfig.CACHE_REDIS_PASSWORD,
    db=2  # 使用单独的数据库存储视频元数据
)

# Redis键前缀
REDIS_VIDEO_KEY_PREFIX = "monitor:video:"
REDIS_VIDEO_INDEX_KEY = "monitor:video:index"

# 确保记录文件夹存在
os.makedirs(RECORD_FOLDER, exist_ok=True)

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

def save_video_metadata(video_data):
    """保存视频元数据到Redis"""
    try:
        # 生成唯一的视频ID
        video_id = f"{int(datetime.now().timestamp())}_{video_data.get('filename', '')}"
        
        # 准备视频元数据
        metadata = {
            'id': video_id,
            'filename': video_data.get('filename', ''),
            'path': video_data.get('path', ''),
            'url': video_data.get('url', ''),
            'size': video_data.get('size', '0MB'),
            'created_at': video_data.get('created', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            'timestamp': video_data.get('timestamp', ''),
            'duration': video_data.get('duration', '00:00:00'),
            'detection_results': video_data.get('detection_results', []),
            'tags': video_data.get('tags', []),
            'is_processed': video_data.get('is_processed', True)
        }
        
        # 将元数据保存到Redis
        redis_key = f"{REDIS_VIDEO_KEY_PREFIX}{video_id}"
        redis_client.set(redis_key, json.dumps(metadata))
        
        # 将视频ID添加到索引列表中
        redis_client.zadd(REDIS_VIDEO_INDEX_KEY, {video_id: int(datetime.now().timestamp())})
        
        return {'success': True, 'video_id': video_id}
    except Exception as e:
        print(f"[Redis错误] 保存视频元数据失败: {str(e)}")
        return {'success': False, 'error': str(e)}

def get_video_metadata(video_id):
    """从Redis获取视频元数据"""
    try:
        redis_key = f"{REDIS_VIDEO_KEY_PREFIX}{video_id}"
        metadata_json = redis_client.get(redis_key)
        
        if not metadata_json:
            return None
            
        return json.loads(metadata_json)
    except Exception as e:
        print(f"[Redis错误] 获取视频元数据失败: {str(e)}")
        return None

def get_all_videos(start=0, limit=20, tag=None):
    """获取所有视频元数据，支持分页和标签筛选"""
    try:
        # 获取按时间戳排序的视频ID列表（最新的排在前面）
        video_ids = redis_client.zrevrange(REDIS_VIDEO_INDEX_KEY, start, start + limit - 1)
        
        videos = []
        for video_id in video_ids:
            video_id = video_id.decode('utf-8') if isinstance(video_id, bytes) else video_id
            metadata = get_video_metadata(video_id)
            
            if metadata and (not tag or tag in metadata.get('tags', [])):
                videos.append(metadata)
                
        return videos
    except Exception as e:
        print(f"[Redis错误] 获取所有视频元数据失败: {str(e)}")
        return []

def delete_video_metadata(video_id):
    """删除Redis中的视频元数据"""
    try:
        redis_key = f"{REDIS_VIDEO_KEY_PREFIX}{video_id}"
        
        # 从Redis删除元数据
        redis_client.delete(redis_key)
        
        # 从索引中移除
        redis_client.zrem(REDIS_VIDEO_INDEX_KEY, video_id)
        
        return {'success': True}
    except Exception as e:
        print(f"[Redis错误] 删除视频元数据失败: {str(e)}")
        return {'success': False, 'error': str(e)}

def sync_videos_with_redis():
    """同步文件系统中的视频与Redis数据库"""
    try:
        if not os.path.exists(RECORD_FOLDER):
            os.makedirs(RECORD_FOLDER, exist_ok=True)
            print(f"[监控回放] 创建记录文件夹: {RECORD_FOLDER}")
            return {'success': True, 'message': '创建文件夹完成', 'count': 0}
            
        # 输出调试信息
        print(f"[监控回放] 开始同步文件夹: {RECORD_FOLDER}")
        
        # 获取文件系统中的所有视频文件
        fs_videos = {}
        video_count = 0
        
        try:
            files = os.listdir(RECORD_FOLDER)
            print(f"[监控回放] 发现文件数量: {len(files)}")
            
            for file in files:
                if file.lower().endswith(('.mp4', '.webm', '.avi', '.mov', '.mkv')):
                    video_count += 1
                    full_path = os.path.join(RECORD_FOLDER, file)
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
                    
                    fs_videos[file] = {
                        'filename': file,
                        'path': os.path.join(RECORD_FOLDER, file),
                        'url': f"/media/record/{file}",
                        'size': f"{size_mb:.2f}MB",
                        'created': create_time.strftime("%Y-%m-%d %H:%M:%S"),
                        'timestamp': timestamp_str or create_time.strftime("%Y-%m-%d %H:%M:%S")
                    }
            
            print(f"[监控回放] 发现视频文件数量: {video_count}")
        except Exception as e:
            print(f"[监控回放] 读取文件夹出错: {str(e)}")
            return {'success': False, 'error': f"读取文件夹出错: {str(e)}"}
        
        # 尝试连接Redis并获取所有视频ID
        try:
            # 测试Redis连接
            redis_client.ping()
            print("[监控回放] Redis连接成功")
            
            redis_videos = redis_client.zrange(REDIS_VIDEO_INDEX_KEY, 0, -1)
            redis_videos = [vid.decode('utf-8') if isinstance(vid, bytes) else vid for vid in redis_videos]
            print(f"[监控回放] Redis中存储的视频数量: {len(redis_videos)}")
        except Exception as e:
            print(f"[监控回放] Redis连接或查询出错: {str(e)}")
            # 如果Redis连接失败，仍然尝试保存所有文件系统中的视频
            redis_videos = []
        
        # 添加文件系统中有但Redis中没有的视频
        added_count = 0
        for file, video_data in fs_videos.items():
            try:
                found = False
                for video_id in redis_videos:
                    metadata = get_video_metadata(video_id)
                    if metadata and metadata.get('filename') == file:
                        found = True
                        break
                        
                if not found:
                    # 保存新视频元数据
                    save_result = save_video_metadata(video_data)
                    if save_result.get('success', False):
                        added_count += 1
                        print(f"[监控回放] 添加新视频: {file}, ID: {save_result.get('video_id')}")
            except Exception as e:
                print(f"[监控回放] 处理视频文件出错: {file}, 错误: {str(e)}")
                
        # 删除Redis中有但文件系统中没有的视频
        removed_count = 0
        for video_id in redis_videos:
            try:
                metadata = get_video_metadata(video_id)
                if metadata and metadata.get('filename') not in fs_videos:
                    delete_video_metadata(video_id)
                    removed_count += 1
                    print(f"[监控回放] 删除不存在的视频记录: {metadata.get('filename', video_id)}")
            except Exception as e:
                print(f"[监控回放] 处理Redis记录出错: {video_id}, 错误: {str(e)}")
                
        print(f"[监控回放] 同步完成，添加: {added_count}, 删除: {removed_count}, 总共: {len(fs_videos)}")
        return {'success': True, 'message': f'同步完成，添加: {added_count}, 删除: {removed_count}, 总共: {len(fs_videos)}'}
    except Exception as e:
        print(f"[监控回放] 同步视频元数据失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}

@bp.route('/playback')
@login_required
def playback():
    """监控回放页面"""
    
    # 确保视频记录目录存在
    os.makedirs(RECORD_FOLDER, exist_ok=True)
    
    # 同步文件系统和Redis数据库
    sync_result = sync_videos_with_redis()
    print(f"[监控回放] 同步结果: {sync_result}")
    
    # 从Redis获取所有视频
    video_files = get_all_videos(0, 100)
    print(f"[监控回放] 获取到视频数量: {len(video_files)}")
    
    return render_template('stream/playback.html', video_files=video_files)

@bp.route('/api/playback/videos')
@login_required
def get_playback_videos():
    """API: 获取所有可回放的视频列表"""
    try:
        # 获取查询参数
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        tag = request.args.get('tag', None)
        force_sync = request.args.get('sync', 'false').lower() == 'true'
        
        # 计算起始索引
        start = (page - 1) * limit
        
        # 同步文件系统和Redis数据库
        if force_sync:
            print(f"[监控回放API] 触发强制同步")
            sync_result = sync_videos_with_redis()
            print(f"[监控回放API] 强制同步结果: {sync_result}")
        else:
            sync_result = sync_videos_with_redis()
            print(f"[监控回放API] 常规同步结果: {sync_result}")
        
        # 获取视频列表
        videos = get_all_videos(start, limit, tag)
        print(f"[监控回放API] 获取到视频数量: {len(videos)}")
        
        # 计算总视频数
        try:
            total_count = redis_client.zcard(REDIS_VIDEO_INDEX_KEY)
        except Exception as e:
            print(f"[监控回放API] 获取视频总数出错: {str(e)}")
            total_count = len(videos)
        
        return jsonify({
            'status': 'success',
            'data': videos,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total_count,
                'pages': max(1, (total_count + limit - 1) // limit)
            },
            'sync_result': sync_result
        })
    except Exception as e:
        print(f"[监控回放API] 获取视频列表出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': f"获取视频列表失败: {str(e)}"
        }), 500

@bp.route('/api/playback/video/<video_id>')
@login_required
def get_video_details(video_id):
    """API: 获取单个视频的详细信息"""
    try:
        metadata = get_video_metadata(video_id)
        
        if not metadata:
            return jsonify({
                'status': 'error',
                'message': '视频不存在'
            }), 404
            
        return jsonify({
            'status': 'success',
            'data': metadata
        })
    except Exception as e:
        print(f"[监控回放API] 获取视频详情失败: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"获取视频详情失败: {str(e)}"
        }), 500

@bp.route('/api/playback/delete/<video_id>', methods=['DELETE'])
@login_required
def delete_playback_video(video_id):
    """API: 删除回放视频"""
    try:
        # 获取视频元数据
        metadata = get_video_metadata(video_id)
        
        if not metadata:
            return jsonify({
                'status': 'error',
                'message': '视频不存在'
            }), 404
            
        # 删除文件系统中的视频文件
        filename = metadata.get('filename', '')
        if filename:
            file_path = os.path.join(RECORD_FOLDER, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                
        # 删除Redis中的元数据
        result = delete_video_metadata(video_id)
        
        if not result.get('success', False):
            return jsonify({
                'status': 'error',
                'message': result.get('error', '删除元数据失败')
            }), 500
            
        return jsonify({
            'status': 'success',
            'message': '视频删除成功'
        })
    except Exception as e:
        print(f"[监控回放API] 删除视频失败: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"删除视频失败: {str(e)}"
        }), 500

@bp.route('/api/playback/tag', methods=['POST'])
@login_required
def add_video_tag():
    """API: 为视频添加标签"""
    try:
        data = request.get_json()
        video_id = data.get('video_id')
        tag = data.get('tag')
        
        if not video_id or not tag:
            return jsonify({
                'status': 'error',
                'message': '缺少必要参数'
            }), 400
            
        # 获取视频元数据
        metadata = get_video_metadata(video_id)
        
        if not metadata:
            return jsonify({
                'status': 'error',
                'message': '视频不存在'
            }), 404
            
        # 添加标签
        tags = metadata.get('tags', [])
        if tag not in tags:
            tags.append(tag)
            metadata['tags'] = tags
            
            # 保存更新后的元数据
            redis_key = f"{REDIS_VIDEO_KEY_PREFIX}{video_id}"
            redis_client.set(redis_key, json.dumps(metadata))
            
        return jsonify({
            'status': 'success',
            'message': '标签添加成功',
            'tags': tags
        })
    except Exception as e:
        print(f"[监控回放API] 添加标签失败: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"添加标签失败: {str(e)}"
        }), 500

# 添加媒体文件访问路由
@bp.route('/media/<path:filename>')
def media_file(filename):
    """提供媒体文件访问"""
    return send_from_directory(BaseConfig.MEDIA_ROOT, filename)

# 添加视频缩略图访问路由
@bp.route('/media/record/thumbnails/<path:filename>')
def video_thumbnail(filename):
    """提供视频缩略图访问"""
    thumbnail_dir = os.path.join(RECORD_FOLDER, 'thumbnails')
    return send_from_directory(thumbnail_dir, filename)

# 添加原始视频文件访问路由
@bp.route('/media/record/<path:filename>')
def video_file(filename):
    """提供原始视频文件访问"""
    return send_from_directory(RECORD_FOLDER, filename)