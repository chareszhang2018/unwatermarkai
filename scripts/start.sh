#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
  echo "未找到 .venv，请先运行: python3 -m venv .venv && source .venv/bin/activate && pip install -e ."
  exit 1
fi

source .venv/bin/activate

# Load HF mirror / token from .env if present
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

PORT="${PORT:-8080}"
if lsof -i ":${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "端口 ${PORT} 已被占用。可先执行: lsof -i :${PORT}"
  echo "或换端口启动: PORT=8081 ./scripts/start.sh"
  exit 1
fi

echo "启动服务: http://127.0.0.1:${PORT}  (PIPELINE=${PIPELINE:-sdxl})"
echo "模型将在首次处理图片时加载（约 8-13 GB 内存），不会启动时预加载。"
echo "开发热重载: RELOAD=1 ./scripts/start.sh"

UVICORN_ARGS=(app.main:app --host 127.0.0.1 --port "${PORT}")
if [ "${RELOAD:-0}" = "1" ]; then
  UVICORN_ARGS+=(--reload)
fi
exec uvicorn "${UVICORN_ARGS[@]}"
