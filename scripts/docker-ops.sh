#!/usr/bin/env bash
# Dashboard 独立运维脚本
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "已创建 .env — 请编辑并填写 XUNJI_API_KEY 后再启动"
  echo "  编辑: $ROOT/.env"
  exit 1
fi

# 读取 .env（忽略注释与空行）
set -a
# shellcheck disable=SC1091
source <(grep -vE '^\s*(#|$)' .env | sed 's/\r$//' || true)
set +a

require_key() {
  if [[ -z "${XUNJI_API_KEY:-}" ]]; then
    echo "错误: .env 中未设置 XUNJI_API_KEY"
    echo "请在训记 App 申请 Open API Key，填入 .env 后重试。"
    exit 1
  fi
}

cmd="${1:-help}"

case "$cmd" in
  up)
    require_key
    docker compose up -d --build
    echo ""
    echo "Dashboard 已启动 → http://localhost:${DASHBOARD_PORT:-8080}"
    echo "局域网访问 → http://<主机IP>:${DASHBOARD_PORT:-8080}"
    echo "首次使用请在总览页点击「增量同步训练数据」"
    ;;
  down)
    docker compose down
    ;;
  restart)
    docker compose restart dashboard
    ;;
  logs)
    docker compose logs -f dashboard
    ;;
  status)
    docker compose ps
    curl -sf "http://127.0.0.1:${DASHBOARD_PORT:-8080}/api/health" | python3 -m json.tool 2>/dev/null || echo "服务未响应"
    ;;
  refresh)
    curl -sf -X POST "http://127.0.0.1:${DASHBOARD_PORT:-8080}/api/refresh" | python3 -m json.tool
    echo "分析数据已刷新"
    ;;
  rebuild)
    require_key
    docker compose down
    docker compose build --no-cache
    docker compose up -d
    ;;
  help|*)
    cat <<'EOF'
用法: scripts/docker-ops.sh <命令>

  up       构建并启动（需已配置 XUNJI_API_KEY）
  down     停止并移除容器
  restart  重启服务
  logs     查看日志
  status   查看状态 + 健康检查
  refresh  重新聚合 analysis.json
  rebuild  无缓存重建镜像

首次部署:
  cp .env.example .env
  # 编辑 .env，填写 XUNJI_API_KEY=xjllm_...
  ./scripts/docker-ops.sh up
EOF
    ;;
esac
