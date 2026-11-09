#!/usr/bin/env bash
# 重启恢复检查钩子：verify.sh 负责起停/杀进程/比对，这里只提供 start/write/read/stop。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/backend/.venv/bin/python"
PORT="${RESTART_CHECK_PORT:-8020}"
if [[ -z "${RESTART_CHECK_DIR:-}" ]]; then
  echo "RESTART_CHECK_DIR 未设置" >&2
  exit 1
fi
DATA="$RESTART_CHECK_DIR"
mkdir -p "$DATA"
export DATABASE_URL="sqlite:///$DATA/app.db"
export APP_ENV="test"
export MODEL_API_KEY="fake-for-test"
export READ_ONLY_MODE="true"

start() {
  if [[ ! -x "$VENV" ]]; then
    echo "缺少 backend/.venv，先安装依赖" >&2
    exit 1
  fi
  if curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
    echo "端口 $PORT 已被占用，无法启动测试实例" >&2
    exit 1
  fi
  cd "$ROOT/backend"
  nohup "$VENV" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" >"$DATA/server.log" 2>&1 &
  pid=$!
  echo "$pid" >"$DATA/server.pid"
  for _ in $(seq 1 60); do
    if curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
      echo "$pid"
      return 0
    fi
    sleep 0.5
  done
  echo "服务启动失败，日志：" >&2
  tail -n 30 "$DATA/server.log" >&2 || true
  kill "$pid" >/dev/null 2>&1 || true
  exit 1
}

write() {
  local marker="${1:?缺少标记}"
  local body
  body=$(printf '{"title":"%s"}' "$marker")
  local resp
  resp=$(curl -fsS -X POST "http://127.0.0.1:$PORT/api/sessions" -H 'Content-Type: application/json' -d "$body")
  python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$resp"
}

read_id() {
  local sid="${1:?缺少会话 ID}"
  local resp
  resp=$(curl -fsS "http://127.0.0.1:$PORT/api/sessions/$sid")
  python3 -c 'import json,sys; print(json.load(sys.stdin)["title"])' <<<"$resp"
}

stop() {
  if [[ -f "$DATA/server.pid" ]]; then
    local pid
    pid=$(cat "$DATA/server.pid")
    kill "$pid" >/dev/null 2>&1 || true
    rm -f "$DATA/server.pid"
  fi
  echo "stopped"
}

case "${1:-}" in
  start) start ;;
  write) write "${2:-}" ;;
  read) read_id "${2:-}" ;;
  stop) stop ;;
  *) echo "用法：$0 start|write <标记>|read <ID>|stop" >&2; exit 2 ;;
esac
