#!/bin/bash
# wecom2notes 部署脚本
# 在项目根目录运行

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 读取端口配置
APP_PORT=${APP_PORT:-8001}

echo "开始构建和启动 wecom2notes..."
echo "端口: $APP_PORT"

# 执行 docker-compose
APP_PORT=$APP_PORT docker-compose up -d --build --force-recreate

echo "部署完成！"
echo "访问地址: http://localhost:$APP_PORT"
