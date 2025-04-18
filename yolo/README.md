# 智能交通监控系统

本项目是一个基于YOLO模型的智能交通监控系统，能够实现车辆类型检测、车牌识别、超速检测和交通事故检测。系统支持实时视频流处理，并通过MQTT协议发送报警信息。

## 功能特点

- **车辆类型检测**：识别车辆类型（轿车、卡车、公交车、摩托车等）
- **车牌识别**：自动识别车辆牌照
- **超速检测**：估算车速并检测超速车辆
- **事故检测**：检测交通事故并报警
- **MQTT报警**：通过MQTT发送超速和事故报警信息
- **Web集成**：与Web应用程序集成，提供实时监控界面
- **数据记录**：保存检测结果、事件日志和报警图像

## 系统架构

系统由以下主要模块组成：

1. **车辆检测模块**（`vehicle_detector_module.py`）：核心模块，实现所有检测功能
2. **Web集成模块**（`web_integration.py`）：提供Web接口，便于集成到现有系统
3. **MQTT客户端**：发送报警信息到智能喇叭等设备

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

### 作为独立模块使用

```python
from vehicle_detector_module import VehicleDetectorModule

# 创建检测器
detector = VehicleDetectorModule(model_path='models/ZHLK_110.onnx')

try:
    # 处理视频文件
    detector.process_video("test_video.mp4", output_path="output_video.mp4")
    
    # 处理单张图像
    detector.process_image("test_image.jpg", output_path="output_image.jpg")
    
    # 处理摄像头实时流
    detector.process_camera(0, output_path="camera_recording.mp4")
    
finally:
    # 释放资源
    detector.close()
```

### 通过Web接口使用

1. 启动Web服务器：

```bash
python web_integration.py
```

2. 在浏览器中访问：http://localhost:5000

3. 通过Web界面上传图像、视频或查看实时摄像头画面

## MQTT配置

系统使用MQTT协议发送报警信息。MQTT服务器配置如下：

- 服务器地址：mqtt://8.138.192.81
- 端口：1883
- 客户端ID：mqttx_61b71c4d

系统发布的主题：
- `overspeed`：超速报警
- `accident`：事故报警

## 目录结构

```
├── models/                  # 模型文件
│   └── ZHLK_110.onnx       # YOLO模型（ONNX格式）
│   └── yolo11s.onnx        # 轻量级YOLO模型（ONNX格式）
├── scripts/                 # 功能脚本
│   └── license_plate_recog_picture.py  # 车牌识别（图片）
│   └── license_plate_recog_video.py    # 车牌识别（视频）
│   └── speed_estimation_and_detect_overspeed.py  # 超速检测
│   └── show_license_annotation_CCPD.py # 车牌注释显示
├── logs/                    # 日志文件
├── detections/              # 检测结果
│   └── accident/           # 事故检测结果
│   └── overspeed/          # 超速检测结果
├── uploads/                 # Web上传文件
├── vehicle_detector_module.py  # 主模块
├── web_integration.py       # Web集成
└── README.md               # 说明文档
```

## 自定义配置

在 `vehicle_detector_module.py` 中可以修改以下参数：

- `self.speed_limit`：速度限制（km/h）
- `self.accident_confidence_threshold`：事故检测置信度阈值

## 注意事项

1. 确保安装了所有依赖包
2. 模型文件较大，请确保有足够的内存
3. 对于实时处理，建议使用GPU加速

## 故障排除

- **模型加载失败**：检查模型文件路径是否正确
- **MQTT连接失败**：检查MQTT服务器配置和网络连接
- **摄像头无法打开**：确认摄像头设备ID和权限

## 许可证

##
OpenCV 的 VideoCapture 类支持多种视频源格式，包括：
本地视频文件（如 .mp4, .avi 等）
摄像头设备（通过设备ID，如 0, 1 等）
网络视频流（如 RTSP, RTMP, HTTP 等）
对于网络视频流，您只需要将 URL 作为参数传递给 VideoCapture，例如：
# RTSP 流
cap = cv2.VideoCapture("rtsp://username:password@192.168.1.100:554/stream")

# RTMP 流
cap = cv2.VideoCapture("rtmp://server.com/live/stream")

# HTTP 流
cap = cv2.VideoCapture("http://server.com/stream.m3u8")

在 vehicle_detector_module.py 中，process_video 方法接受一个 video_path 参数，这个参数可以是本地文件路径，也可以是网络视频流的 URL。同样，process_camera 方法接受一个 camera_id 参数，这个参数可以是摄像头设备 ID，也可以是网络视频流的 URL。
因此，您可以直接使用这些方法来处理 RTSP、RTMP 等网络视频流，只需将相应的 URL 作为参数传递即可。例如：

detector = VehicleDetectorModule()
detector.process_video("rtsp://username:password@192.168.1.100:554/stream")

##

MIT 