import subprocess
import threading
import logging
import time
import os
import signal
import re
from datetime import datetime

class StreamManager:
    """流媒体管理器，用于处理RTMP推流相关操作"""
    
    def __init__(self):
        self.active_processes = {}
        self.logger = logging.getLogger('stream_manager')
    
    def push_ipcam_to_srs(self, camera_url, rtmp_url, stream_id=None, video_params=None):
        """
        将IP摄像头推送到SRS流媒体服务器
        
        Args:
            camera_url: IP摄像头的RTSP URL
            rtmp_url: SRS服务器的RTMP URL
            stream_id: 自定义流ID，如果为None则随机生成
            video_params: 视频参数字典，可包含以下键：
                - video_codec: 视频编码器 (默认: copy)
                - video_bitrate: 视频比特率 (默认: 不设置)
                - video_size: 视频尺寸 (默认: 不设置)
                - video_framerate: 视频帧率 (默认: 不设置)
                - audio_codec: 音频编码器 (默认: aac)
                - audio_bitrate: 音频比特率 (默认: 不设置)
                - audio_sample_rate: 音频采样率 (默认: 44100)
                - audio_channels: 音频通道数 (默认: 1)
        
        Returns:
            dict: 包含状态和消息的字典
        """
        if not self._is_valid_rtsp_url(camera_url):
            return {
                "success": False,
                "message": "无效的RTSP URL格式"
            }
        
        # 如果已经有相同的推流任务，先停止它
        if stream_id in self.active_processes:
            self.stop_push(stream_id)
        
        # 生成唯一的流ID，如果没有提供
        if stream_id is None:
            stream_id = f"ipcam_{int(time.time())}"
        
        # 设置默认参数
        if video_params is None:
            video_params = {}
        
        # 获取视频参数
        video_codec = video_params.get('video_codec', 'copy')
        video_bitrate = video_params.get('video_bitrate', None)
        video_size = video_params.get('video_size', None)
        video_framerate = video_params.get('video_framerate', None)
        audio_codec = video_params.get('audio_codec', 'aac')
        audio_bitrate = video_params.get('audio_bitrate', None)
        audio_sample_rate = video_params.get('audio_sample_rate', '44100')
        audio_channels = video_params.get('audio_channels', '1')
        
        try:
            # 构建FFmpeg命令
            command = [
                'ffmpeg',
                '-re',
                '-i', camera_url,
            ]
            
            # 添加视频编码参数
            command.extend(['-c:v', video_codec])
            
            # 如果不是copy模式，添加更多视频参数
            if video_codec != 'copy':
                if video_bitrate:
                    command.extend(['-b:v', video_bitrate])
                if video_size:
                    command.extend(['-s', video_size])
                if video_framerate:
                    command.extend(['-r', video_framerate])
            
            # 添加音频编码参数
            command.extend(['-c:a', audio_codec])
            
            # 添加音频参数
            if audio_bitrate:
                command.extend(['-b:a', audio_bitrate])
            if audio_sample_rate:
                command.extend(['-ar', audio_sample_rate])
            if audio_channels:
                command.extend(['-ac', audio_channels])
            
            # 添加输出格式参数
            command.extend([
                '-f', 'flv',
                '-flvflags', 'no_duration_filesize',
                '-y',
                rtmp_url
            ])
            
            # 创建一个子进程来运行FFmpeg
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # 存储进程信息
            self.active_processes[stream_id] = {
                'process': process,
                'camera_url': camera_url,
                'rtmp_url': rtmp_url,
                'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'video_params': video_params
            }
            
            # 启动一个线程来监控进程输出
            def monitor_process():
                for line in process.stderr:
                    if "error" in line.lower():
                        self.logger.error(f"FFmpeg错误 [{stream_id}]: {line.strip()}")
            
            monitor_thread = threading.Thread(target=monitor_process)
            monitor_thread.daemon = True
            monitor_thread.start()
            
            # 等待一段时间，确保推流成功启动
            time.sleep(2)
            
            # 检查进程是否仍在运行
            if process.poll() is not None:
                error_output = process.stderr.read()
                self.logger.error(f"FFmpeg进程终止 [{stream_id}]: {error_output}")
                return {
                    "success": False,
                    "message": f"推流失败: {error_output}"
                }
            
            return {
                "success": True,
                "message": "成功将IP摄像头推送到流媒体服务器",
                "stream_id": stream_id,
                "rtmp_url": rtmp_url,
                "video_params": video_params
            }
            
        except Exception as e:
            self.logger.exception(f"推流过程中发生错误 [{stream_id}]: {str(e)}")
            return {
                "success": False,
                "message": f"推流过程中发生错误: {str(e)}"
            }
    
    def stop_push(self, stream_id):
        """
        停止指定的推流任务
        
        Args:
            stream_id: 要停止的流ID
        
        Returns:
            dict: 包含状态和消息的字典
        """
        if stream_id not in self.active_processes:
            return {
                "success": False,
                "message": f"找不到ID为 {stream_id} 的推流任务"
            }
        
        try:
            process_info = self.active_processes[stream_id]
            process = process_info['process']
            
            # 在Windows上使用taskkill
            if os.name == 'nt':
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)])
            # 在Unix/Linux上使用SIGTERM信号
            else:
                os.kill(process.pid, signal.SIGTERM)
            
            # 等待进程终止
            process.wait(timeout=5)
            
            # 从活动进程列表中移除
            del self.active_processes[stream_id]
            
            return {
                "success": True,
                "message": f"成功停止ID为 {stream_id} 的推流任务"
            }
            
        except Exception as e:
            self.logger.exception(f"停止推流任务时发生错误 [{stream_id}]: {str(e)}")
            return {
                "success": False,
                "message": f"停止推流任务时发生错误: {str(e)}"
            }
    
    def get_active_streams(self):
        """获取所有活动的流媒体信息"""
        active_streams = []
        for stream_id, process_info in self.active_processes.items():
            stream_info = {
                'stream_id': stream_id,
                'camera_url': process_info.get('camera_url', ''),
                'rtmp_url': process_info.get('rtmp_url', ''),
                'start_time': process_info.get('start_time', ''),
                'runtime': self._format_runtime(process_info.get('start_time', '')),
                'status': 'active' if process_info.get('process', None) and process_info['process'].poll() is None else 'stopped',
                'video_params': process_info.get('video_params', {})
            }
            active_streams.append(stream_info)
        return active_streams
    
    def _format_runtime(self, start_time):
        """格式化运行时间"""
        if not start_time:
            return '0:00:00'
        
        try:
            start = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
            now = datetime.now()
            delta = now - start
            
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60
            seconds = delta.seconds % 60
            
            return f'{hours}:{minutes:02d}:{seconds:02d}'
        except:
            return '0:00:00'
    
    def _is_valid_rtsp_url(self, url):
        """
        检查是否是有效的RTSP URL
        
        Args:
            url: 要检查的URL
        
        Returns:
            bool: 是否是有效的RTSP URL
        """
        # 简单检查URL是否以rtsp://开头
        if not url.lower().startswith('rtsp://'):
            return False
        
        # 可以添加更复杂的验证逻辑
        rtsp_pattern = r'^rtsp://(?:[\w\-\.]+(?::\w+)?@)?[\w\-\.]+(?::\d+)?(?:/[\w\-\.]+)*/?(?:\?[\w\-\.=&]+)?$'
        return bool(re.match(rtsp_pattern, url))

# 创建全局实例
stream_manager = StreamManager() 