#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PORT="${DASHBOARD_PORT:-8080}"
PIDFILE="$ROOT/.dashboard.pid"
cmd="${1:-help}"

start_server() {
  if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "already running pid $(cat "$PIDFILE")"
    return
  fi
  if lsof -i ":$PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "port $PORT in use, run stop first"
    exit 1
  fi
  [[ -f data/analysis.json ]] || python3 scripts/analyze.py
  [[ -d web/dist ]] || (cd web && npm install && npm run build)
  nohup python3 -m uvicorn server.main:app --host 0.0.0.0 --port "$PORT" \
    > "$ROOT/.dashboard.log" 2>&1 &
  echo $! > "$PIDFILE"
  sleep 1
  curl -sf "http://127.0.0.1:$PORT/api/health" | python3 -m json.tool
  echo "http://127.0.0.1:$PORT"
}

case "$cmd" in
  up|start)
    start_server
    ;;
  down|stop)
    if [[ -f "$PIDFILE" ]]; then
      kill "$(cat "$PIDFILE")" 2>/dev/null || true
      rm -f "$PIDFILE"
    fi
    lsof -i ":$PORT" -sTCP:LISTEN -t 2>/dev/null | xargs kill 2>/dev/null || true
    echo "stopped"
    ;;
  restart)
    "$0" stop
    sleep 1
    "$0" start
    ;;
  status)
    curl -sf "http://127.0.0.1:$PORT/api/health" | python3 -m json.tool 2>/dev/null || echo "not running"
    ;;
  refresh)
    curl -sf -X POST "http://127.0.0.1:$PORT/api/refresh" | python3 -m json.tool
    ;;
  logs)
    tail -f "$ROOT/.dashboard.log"
    ;;
  *)
    echo "usage: local-ops.sh up|stop|restart|status|refresh|logs"
    ;;
esac
