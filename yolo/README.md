# YOLO车辆检测与交通监控系统

## 项目概述

本项目是一个基于YOLO（You Only Look Once）目标检测算法的实时交通监控系统，能够对视频流进行处理，识别车辆、检测交通事故，并支持车牌识别等功能。系统采用Flask作为Web框架，提供REST API和WebSocket接口，可与前端应用或其他系统集成。

## 主要功能

- **实时视频分析**：支持各种格式的视频流处理
- **多目标检测**：
  - 车辆检测与分类
  - 交通事故检测
  - 车牌识别与OCR
  - 车辆颜色识别
- **多模型支持**：支持多种YOLO模型（ONNX和PyTorch格式）
- **MQTT告警**：检测到事故后可通过MQTT发送告警信息
- **WebSocket实时推送**：支持检测结果的实时推送
- **REST API**：提供图像和视频分析的HTTP接口
- **GPU加速**：支持CUDA加速，提高处理效率

## 技术栈

- **视觉模型**：YOLO目标检测模型（ONNX和PyTorch格式）
- **Web框架**：Flask
- **实时通信**：WebSocket（Flask-SocketIO）
- **告警通知**：MQTT协议
- **图像处理**：OpenCV
- **深度学习框架**：PyTorch
- **容器化**：Docker

## 项目结构

```
yolo/
├── app.py                # 主应用入口文件
├── detection/            # 检测模块目录
│   ├── __init__.py       # 模块初始化文件
│   ├── detector.py       # 核心检测器实现
│   ├── video_processor.py # 视频处理逻辑
│   ├── image_processor.py # 图像处理逻辑
│   ├── license_plate_ocr.py # 车牌OCR实现
│   ├── vehicle_analyzer.py # 车辆分析（如颜色识别）
│   └── class_mapper.py   # 类别映射
├── utils/               # 工具函数
│   ├── __init__.py
│   └── mqtt_module.py   # MQTT客户端模块
├── models/              # 预训练模型目录
│   ├── zhlkv3.onnx      # 主要使用的ONNX模型
│   └── ... (其他模型文件)
├── temp_videos/         # 临时上传的视频文件
├── Dockerfile           # Docker配置文件
├── docker-compose.yml   # Docker Compose配置
├── requirements.txt     # 项目依赖
└── simhei.ttf           # 中文字体文件
```

## API接口

### REST API

- `GET /`: 首页
- `GET /healthcheck`: 健康检查接口
- `GET /api/status`: 获取服务器状态
- `POST /img_predict`: 图像检测API
- `POST /video_predict`: 视频检测API
- `GET /download/<filename>`: 下载处理后的视频
- `GET /stream/<filename>`: 流式传输处理后的视频

### WebSocket事件

- 连接事件: 建立WebSocket连接
- 视频质量更新: 动态调整视频质量
- 检测结果推送: 实时推送检测结果

## 安装与部署

### 使用Docker（推荐）

```bash
# 构建并启动容器
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 手动安装

1. 安装依赖:
```bash
pip install -r requirements.txt
```

2. 确保模型文件放置在 `models/` 目录下

3. 启动应用:
```bash
python app.py
```

## 配置项

主要配置可在 `app.py` 中修改:

- 默认使用的模型: `models/zhlkv3.onnx`
- MQTT配置: 服务器地址、端口和主题
- 视频处理参数: 帧率、分辨率、质量等
- 检测阈值和其他参数

## 性能优化

- GPU加速: 自动检测并使用CUDA加速
- 批处理: 支持图像批量处理
- 帧跳过: 处理时可跳过部分帧以提高效率
- 动态质量调整: 根据负载调整视频质量

## 注意事项

- 系统默认使用GPU加速，无GPU环境将自动切换到CPU模式
- 临时文件会在一小时后自动清理
- 建议使用较新版本的CUDA和PyTorch以获得最佳性能


