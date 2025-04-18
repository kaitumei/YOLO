# Flask服务器应用

这是一个基于Flask框架构建的服务器应用。

## 功能特点

- 内容管理系统路由
- 通用功能路由（登录/注册等）
- 前端展示路由
- 服务器状态监控：CPU、内存、磁盘使用情况

## 安装要求

```bash
pip install -r requirements.txt
```

### 依赖项

- Python 3.8+
- Flask
- Flask-Migrate
- Flask-WTF
- Flask-SocketIO
- psutil
- eventlet

## 使用说明

### 1. 启动服务器

```bash
python app.py
```

服务器将在 `http://localhost:5000` 上运行。

### 2. API接口说明

#### 服务器状态

- **URL**: `/api/status`
- **方法**: GET
- **返回**: 服务器资源使用情况

#### 健康检查

- **URL**: `/healthcheck`
- **方法**: GET
- **返回**: 服务器健康状态

## 测试

使用提供的测试脚本测试服务器功能：

```bash
python test_server.py
```

## 文件说明

- `app.py`: 主应用程序
- `test_server.py`: 测试脚本

## 注意事项

- 服务器默认运行在5000端口
- 使用了Flask-SocketIO进行实时通信 