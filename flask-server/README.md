# Flask 服务器

## 项目简介

本项目是一个基于Flask框架开发的多功能Web服务器，包含内容管理系统、用户认证、流媒体处理等功能。项目采用了微服务架构，使用Docker和Docker Compose进行容器化部署，支持高并发和可扩展性。

## 技术栈

- **后端框架**: Flask
- **数据库**: MySQL 8.0
- **缓存系统**: Redis
- **消息队列**: Celery
- **WebSocket**: Flask-SocketIO
- **流媒体服务**: SRS (Simple RTMP Server)
- **反向代理**: Nginx
- **容器化**: Docker & Docker Compose

## 系统架构

系统由以下几个主要组件组成:

1. **Web服务**: 主Flask应用，处理HTTP请求
2. **数据库服务**: 存储应用数据
3. **Redis缓存**: 提供缓存和消息代理功能
4. **Celery工作节点**: 处理异步任务
5. **SRS流媒体服务器**: 处理视频流
6. **微信服务器**: 对接微信平台API
7. **Nginx**: 反向代理和静态资源服务

## 项目结构

```
flask-server/
├── app.py              # 主应用入口
├── celery_worker.py    # Celery工作节点配置
├── celeryconfig.py     # Celery配置文件
├── config/             # 应用配置
├── docker/             # Docker相关配置
├── docker-compose.yml  # 服务编排配置
├── Dockerfile          # Web服务容器构建文件
├── gunicorn.conf.py    # Gunicorn配置
├── logs/               # 日志目录
├── media/              # 媒体文件
├── migrations/         # 数据库迁移文件
├── requirements.txt    # 依赖列表
├── src/                # 源代码目录
│   ├── blueprints/     # 蓝图模块
│   │   ├── check/      # 服务检查
│   │   ├── cms/        # 内容管理
│   │   ├── common/     # 通用功能
│   │   ├── front/      # 前端API
│   │   ├── monitor/    # 监控模块
│   │   └── stream/     # 流媒体处理
│   └── utils/          # 工具函数
├── static/             # 静态资源
└── templates/          # 模板文件
```

## 主要功能

- 用户认证与授权
- 内容管理系统
- 流媒体处理与播放
- 微信平台集成
- 异步任务处理
- 实时通信 (WebSocket)

## 安装与部署

### 前提条件

- Docker 和 Docker Compose
- 正确配置的 `.env` 文件

### 部署步骤

1. 克隆代码库:
   ```bash
   git clone <仓库地址>
   cd flask-server
   ```

2. 配置环境变量:
   ```bash
   cp .env.example .env
   # 编辑 .env 文件，设置必要的环境变量
   ```

3. 启动服务:
   ```bash
   docker-compose up -d
   ```

4. 初始化数据库:
   ```bash
   docker-compose exec web flask db upgrade
   docker-compose exec web flask create-admin
   ```

### 本地开发

1. 创建虚拟环境:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

2. 安装依赖:
   ```bash
   pip install -r requirements.txt
   ```

3. 运行开发服务器:
   ```bash
   flask run
   ```

## 常用命令

- 创建管理员账号: `flask create-admin`
- 创建权限: `flask create-permission`
- 创建角色: `flask create-role`
- 创建测试用户: `flask create-test-user`
- 更新角色权限: `flask update-permissions`

## 接口文档

项目的API接口分为以下几个模块:

- `/api/cms` - 内容管理系统接口
- `/api/common` - 通用功能接口
- `/api/front` - 前端展示接口
- `/api/check` - 服务状态检查接口
- `/api/stream` - 流媒体相关接口

详细的API文档请参考内部文档或代码注释。

## 贡献指南

1. Fork项目
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建Pull Request

## 许可证

[MIT](LICENSE)
