#!/bin/sh
set -e

echo "=== 慧眼通途 Node.js 服务启动脚本 ==="

# 检查工作目录
echo "当前工作目录: $(pwd)"
ls -la

# 确保config目录存在
if [ ! -d "./config" ]; then
  echo "创建config目录"
  mkdir -p ./config
fi

# 检查config目录内容
echo "config目录内容:"
ls -la ./config || echo "config目录为空"

# 检查数据库配置文件
if [ ! -f "./config/db.js" ]; then
  echo "数据库配置文件不存在，将在启动时自动创建"
fi

# 检查依赖项
echo "检查node_modules"
if [ ! -d "./node_modules" ] || [ ! -f "./node_modules/express/package.json" ]; then
  echo "安装依赖"
  npm install
fi

# 检查环境变量
echo "环境变量:"
echo "NODE_ENV: $NODE_ENV"
echo "DB_HOST: $DB_HOST"
echo "DB_PORT: $DB_PORT"
echo "DB_NAME: $DB_NAME"

# 启动应用
echo "启动应用..."
node --trace-warnings start.js 