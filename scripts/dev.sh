#!/usr/bin/env bash
# 가상환경 활성화 → FastAPI(uvicorn) 백그라운드 → Vite 프론트(포그라운드).
# 프로젝트 루트에서 실행: ./scripts/dev.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f "$ROOT/.venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "$ROOT/.venv/bin/activate"
elif [[ -f "$ROOT/venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "$ROOT/venv/bin/activate"
else
  echo "dev.sh: .venv 또는 venv가 없습니다. 프로젝트 루트에 가상환경을 만들고 다시 실행하세요." >&2
  exit 1
fi

BACKEND_PID=""
cleanup() {
  if [[ -n "${BACKEND_PID}" ]] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
    kill "${BACKEND_PID}" 2>/dev/null || true
    wait "${BACKEND_PID}" 2>/dev/null || true
  fi
}~
trap cleanup EXIT INT TERM

echo "dev.sh: 백엔드 http://localhost:8000 (uvicorn --reload)"
uvicorn backend.main:app --reload &
BACKEND_PID=$!

cd "$ROOT/frontend"
echo "dev.sh: 프론트 http://localhost:3000 (npm run dev)"
npm run dev
