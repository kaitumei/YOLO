# 项目启动脚本

这个脚本用于同时启动flask-server和yolo项目中的app.py应用程序。

## 使用方法

### 基本用法

```bash
# 同时启动两个项目（自动安装依赖）
python run_projects.py

# 只启动flask-server项目
python run_projects.py flask-server

# 只启动yolo项目
python run_projects.py yolo

# 启动但不安装依赖
python run_projects.py --no-deps

# 使用简单模式启动（直接使用系统Python而不使用虚拟环境）
python run_projects.py --simple
```

### 脚本功能

- 自动检测并使用项目中的虚拟环境（如果存在）
- 如果虚拟环境不存在或不完整，会自动创建
- 自动处理requirements.txt的编码问题
- 自动安装项目依赖（requirements.txt）
- 支持Windows和Unix/Linux/MacOS系统
- 后台运行应用程序
- 可以单独启动任一项目
- 提供简单模式，直接使用系统Python启动

## 项目说明

### flask-server

Flask服务器是一个多功能Web服务，包含：
- 内容管理系统
- 用户认证
- 流媒体处理
- 微信平台集成
- 异步任务处理
- 实时通信 (WebSocket)

默认运行在本地的5000端口。

### yolo

YOLO项目是一个基于深度学习的图像识别系统，具有：
- 对象检测功能
- 车牌识别
- 事故检测
- MQTT消息发布
- WebSocket实时通信

## 依赖关系

两个项目有各自的依赖，请确保已经安装了各自项目中requirements.txt列出的所有包。

### 快速设置环境（如果尚未设置）

```bash
# 设置flask-server环境
cd flask-server
python -m venv venv
# Windows:
venv\Scripts\activate
# Unix/Linux/MacOS:
source venv/bin/activate
pip install -r requirements.txt
deactivate

# 设置yolo环境
cd ../yolo
python -m venv venv
# Windows:
venv\Scripts\activate
# Unix/Linux/MacOS:
source venv/bin/activate
pip install -r requirements.txt
deactivate

# 返回根目录
cd ..
```

## 注意事项

- 运行脚本时请确保在项目根目录下运行
- 初次运行时将自动安装依赖，可能需要一些时间
- 某些特殊依赖可能需要手动安装：
  - yolo项目中的torch和torchvision依赖使用了特定的CUDA版本，如果安装失败，可能需要手动安装兼容您系统的版本
  - 部分依赖可能需要额外的系统库支持（如OpenCV）
- 使用Ctrl+C可以退出脚本
- 脚本退出后，所有启动的项目进程仍会在后台运行
- 如需完全停止项目，请手动终止相应的进程

## 故障排除

如果遇到依赖安装问题，可以尝试：

1. 使用简单模式启动：
   ```bash
   python run_projects.py --simple
   ```
   
   这将跳过虚拟环境和依赖安装，直接使用系统Python运行项目。使用此模式前，请确保已经手动安装了必要的依赖。

2. 手动安装主要依赖：
   ```bash
   # 基础依赖
   pip install flask flask-cors opencv-python numpy torch torchvision
   ```

3. 如果遇到编码问题，可以尝试手动转换requirements.txt文件编码为UTF-8：
   - 使用记事本或其他编辑器打开requirements.txt
   - 另存为时选择UTF-8编码格式

4. 对于torch和CUDA相关问题：
   ```bash
   # 安装CPU版本的PyTorch（如果不需要GPU加速）
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
   
   # 或安装特定CUDA版本的PyTorch
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
   ``` 