"""
MQTT通信模块

此模块提供与MQTT服务器的通信功能。
"""

import paho.mqtt.client as mqtt
import json
import time
import threading
from queue import Queue, Empty

class MQTTModule:
    def __init__(self, client_id, broker="localhost", port=1883, topic="yolo/detections", qos=0, max_queue_size=100):
        """
        初始化MQTT客户端
        
        参数:
            client_id: 客户端标识符
            broker: MQTT代理服务器地址
            port: MQTT代理服务器端口
            topic: 发布主题
            qos: 服务质量级别(0, 1, 2)
            max_queue_size: 最大队列大小
        """
        self.client_id = client_id
        self.broker = broker
        self.port = port
        self.topic = topic
        self.qos = qos
        try:
            # 尝试使用新版paho-mqtt 2.0+的参数
            self.client = mqtt.Client(client_id=client_id, callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
        except (AttributeError, TypeError):
            # 回退到旧版paho-mqtt的参数
            self.client = mqtt.Client(client_id)
        self.connected = False
        self.paused = False
        self.log_info = print
        self.log_error = print
        
        # 添加消息队列和处理线程
        self.message_queue = Queue(maxsize=max_queue_size)
        self.worker_thread = None
        self.should_stop = False
        
    def set_logger(self, info_logger, error_logger):
        """设置日志函数"""
        self.log_info = info_logger
        self.log_error = error_logger
        
    def connect(self):
        """连接到MQTT代理服务器"""
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            self.connected = True
            
            # 启动消息处理线程
            self.should_stop = False
            self.worker_thread = threading.Thread(target=self._message_worker, daemon=True)
            self.worker_thread.start()
            
            self.log_info(f"MQTT客户端已连接到 {self.broker}:{self.port}")
            return True
        except Exception as e:
            self.log_error(f"MQTT连接失败: {e}")
            self.connected = False
            return False
            
    def disconnect(self):
        """断开MQTT连接"""
        if self.connected:
            # 停止消息处理线程
            self.should_stop = True
            if self.worker_thread and self.worker_thread.is_alive():
                self.worker_thread.join(timeout=2.0)
            
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
            self.log_info("MQTT客户端已断开连接")
            
    def is_connected(self):
        """检查是否已连接"""
        return self.connected
        
    def pause(self):
        """暂停发布"""
        self.paused = True
        self.log_info("MQTT发布已暂停")
        
    def resume(self):
        """恢复发布"""
        self.paused = False
        self.log_info("MQTT发布已恢复")
        
    def is_paused(self):
        """检查是否已暂停"""
        return self.paused
        
    def publish_detection(self, detections, image_base64=None):
        """
        发布检测结果
        
        参数:
            detections: 检测结果列表
            image_base64: 可选的Base64编码图像
        """
        if not self.connected or self.paused:
            return False
            
        try:
            message = {
                "timestamp": time.time(),
                "detections": detections
            }
            
            if image_base64:
                message["image"] = image_base64
                
            # 将消息添加到队列
            try:
                self.message_queue.put_nowait({"topic": self.topic, "message": message, "qos": self.qos})
                return True
            except Queue.Full:
                self.log_error("MQTT消息队列已满，消息被丢弃")
                return False
        except Exception as e:
            self.log_error(f"MQTT发布失败: {e}")
            return False
    
    def publish_batch(self, batch_detections, batch_images=None):
        """
        批量发布多组检测结果
        
        参数:
            batch_detections: 多组检测结果列表
            batch_images: 可选的多组Base64编码图像
        """
        if not self.connected or self.paused:
            return False
        
        success_count = 0
        total_count = len(batch_detections)
        
        try:
            for i, detections in enumerate(batch_detections):
                message = {
                    "timestamp": time.time(),
                    "detections": detections
                }
                
                if batch_images and i < len(batch_images):
                    message["image"] = batch_images[i]
                
                try:
                    self.message_queue.put_nowait({"topic": self.topic, "message": message, "qos": self.qos})
                    success_count += 1
                except Queue.Full:
                    self.log_error("MQTT消息队列已满，剩余消息被丢弃")
                    break
            
            if success_count > 0:
                self.log_info(f"批量发布: 已将 {success_count}/{total_count} 条消息加入队列")
                return True
            return False
        except Exception as e:
            self.log_error(f"MQTT批量发布失败: {e}")
            return False
    
    def _message_worker(self):
        """消息处理线程：从队列读取消息并发布"""
        while not self.should_stop:
            try:
                msg_data = self.message_queue.get(block=True, timeout=0.5)
                if self.connected and not self.paused:
                    topic = msg_data["topic"]
                    message = msg_data["message"]
                    qos = msg_data.get("qos", 0)
                    
                    # 转换为JSON并发布
                    json_message = json.dumps(message)
                    self.client.publish(topic, json_message, qos=qos)
                
                self.message_queue.task_done()
            except Empty:
                # 队列为空，继续等待
                pass
            except Exception as e:
                self.log_error(f"消息处理线程错误: {e}")
                # 短暂休眠，避免在错误情况下CPU使用率过高
                time.sleep(0.1)
    
    def set_topic(self, topic):
        """设置发布主题"""
        self.topic = topic
        self.log_info(f"MQTT主题已更改为: {topic}")
    
    def get_queue_size(self):
        """获取当前队列大小"""
        return self.message_queue.qsize()
    
    def wait_empty(self, timeout=None):
        """等待队列为空"""
        try:
            self.message_queue.join(timeout=timeout)
            return True
        except:
            return False 