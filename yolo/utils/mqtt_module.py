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
    def __init__(self, client_id, broker="117.72.120.52", port=1883, topic="alarm/command", qos=0, max_queue_size=100, keep_alive=60, reconnect_delay=5, clean_session=True):
        """
        初始化MQTT客户端
        
        参数:
            client_id: 客户端标识符
            broker: MQTT代理服务器地址
            port: MQTT代理服务器端口
            topic: 发布主题
            qos: 服务质量级别(0, 1, 2)
            max_queue_size: 最大队列大小
            keep_alive: 保持连接时间(秒)
            reconnect_delay: 重连延迟时间(秒)
            clean_session: 是否使用干净的会话
        """
        self.client_id = client_id
        self.broker = broker
        self.port = port
        self.topic = topic
        self.qos = qos
        self.keep_alive = keep_alive
        self.reconnect_delay = reconnect_delay
        
        # 从MQTT地址删除协议前缀，如果存在
        if self.broker.startswith("mqtt://"):
            self.broker = self.broker[7:]
        
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
            # 设置回调函数
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            
            # 设置自动重连
            self.client.reconnect_delay_set(min_delay=1, max_delay=self.reconnect_delay)
            
            # 连接到服务器
            self.log_info(f"正在连接MQTT服务器: {self.broker}:{self.port}")
            self.client.connect(self.broker, self.port, self.keep_alive)
            self.client.loop_start()
            
            # 启动消息处理线程
            self.should_stop = False
            self.worker_thread = threading.Thread(target=self._message_worker, daemon=True)
            self.worker_thread.start()
            
            return True
        except Exception as e:
            self.log_error(f"MQTT连接失败: {e}")
            self.connected = False
            return False
    
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT连接回调函数"""
        if rc == 0:
            self.connected = True
            self.log_info(f"MQTT客户端已成功连接到 {self.broker}:{self.port}")
        else:
            error_messages = {
                1: "连接被拒绝 - 协议版本错误",
                2: "连接被拒绝 - 客户端标识符无效",
                3: "连接被拒绝 - 服务器不可用",
                4: "连接被拒绝 - 用户名或密码错误",
                5: "连接被拒绝 - 未授权"
            }
            error_msg = error_messages.get(rc, f"未知错误 (代码: {rc})")
            self.log_error(f"MQTT连接失败: {error_msg}")
            self.connected = False
    
    def _on_disconnect(self, client, userdata, rc):
        """MQTT断开连接回调函数"""
        if rc != 0:
            self.log_error(f"MQTT连接意外断开，代码: {rc}，将自动重连")
        else:
            self.log_info("MQTT客户端已正常断开连接")
        self.connected = False
            
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
        
    def publish(self, message_str):
        """
        发布简单字符串消息
        
        参数:
            message_str: 要发布的字符串消息
        """
        if not self.connected or self.paused:
            return False
            
        try:
            # 将消息添加到队列
            try:
                self.message_queue.put_nowait({"topic": self.topic, "message": message_str, "qos": self.qos})
                self.log_info(f"已将消息 '{message_str}' 加入MQTT发布队列")
                return True
            except Queue.Full:
                self.log_error("MQTT消息队列已满，消息被丢弃")
                return False
        except Exception as e:
            self.log_error(f"MQTT发布失败: {e}")
            return False
        
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
            # 精简消息数据，减少传输量
            # 1. 对于image_base64，如果长度超过一定限制，可以减小图像质量或尺寸
            # 2. 对于detections，可以过滤掉低置信度的结果
            
            filtered_detections = []
            if detections and len(detections) > 0:
                # 只保留置信度大于0.4的检测结果
                filtered_detections = [d for d in detections if d.get("confidence", 0) > 0.4]
                
                # 如果过滤后结果为空，但原始检测有结果，保留置信度最高的前3个
                if not filtered_detections and detections:
                    sorted_detections = sorted(detections, key=lambda x: x.get("confidence", 0), reverse=True)
                    filtered_detections = sorted_detections[:min(3, len(sorted_detections))]
            
            message = {
                "timestamp": time.time(),
                "detections": filtered_detections
            }
            
            # 可选地发送图像（较大的数据）
            if image_base64:
                message["image"] = image_base64
            
            # 将消息添加到队列
            try:
                self.message_queue.put_nowait({"topic": self.topic, "message": message, "qos": self.qos})
                return True
            except Queue.Full:
                self.log_error("MQTT消息队列已满，消息被丢弃")
                # 尝试清理队列
                try:
                    # 移除一半的旧消息
                    half_size = self.message_queue.qsize() // 2
                    for _ in range(half_size):
                        try:
                            self.message_queue.get_nowait()
                            self.message_queue.task_done()
                        except Empty:
                            break
                    # 重新尝试添加最新消息
                    self.message_queue.put_nowait({"topic": self.topic, "message": message, "qos": self.qos})
                    self.log_info("已清理消息队列并添加新消息")
                    return True
                except:
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
        retry_count = 0
        max_retries = 3
        
        while not self.should_stop:
            try:
                msg_data = self.message_queue.get(block=True, timeout=0.5)
                
                if self.connected and not self.paused:
                    topic = msg_data["topic"]
                    message = msg_data["message"]
                    qos = msg_data.get("qos", 0)
                    
                    # 处理不同类型的消息
                    if isinstance(message, str):
                        # 字符串消息直接发布
                        payload = message
                    else:
                        # 对象转换为JSON
                        payload = json.dumps(message)
                    
                    # 添加发布重试逻辑
                    publish_success = False
                    retry_attempt = 0
                    
                    while not publish_success and retry_attempt < max_retries:
                        try:
                            self.client.publish(topic, payload, qos=qos)
                            publish_success = True
                        except Exception as e:
                            retry_attempt += 1
                            if retry_attempt < max_retries:
                                self.log_error(f"MQTT发布失败，尝试重试 ({retry_attempt}/{max_retries}): {e}")
                                time.sleep(0.5)  # 短暂延迟后重试
                            else:
                                self.log_error(f"MQTT发布多次失败，放弃: {e}")
                
                self.message_queue.task_done()
                retry_count = 0  # 成功一次后重置重试计数
                
            except Empty:
                # 队列为空，继续等待
                pass
            except Exception as e:
                retry_count += 1
                self.log_error(f"消息处理线程错误: {e}")
                
                if retry_count > 10:
                    self.log_error("检测到多次持续错误，线程将休眠5秒后继续")
                    time.sleep(5)
                    retry_count = 0
                else:
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