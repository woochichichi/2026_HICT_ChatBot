#!/bin/bash
# pre-commit 체크 스크립트
# Claude/Cursor 양쪽에서 커밋 시 자동 실행
# 설치: cp scripts/pre-commit-check.sh .git/hooks/pre-commit

echo "=== pre-commit 체크 시작 ==="

ERRORS=0

# 1. .env 커밋 방지
if git diff --cached --name-only | grep -q "^\.env$"; then
  echo "[FAIL] .env 파일이 커밋에 포함됨 — 민감 정보 유출 위험"
  ERRORS=$((ERRORS + 1))
fi

# 2. data/ 폴더 커밋 방지 (chroma_db, raw)
if git diff --cached --name-only | grep -qE "^data/(chroma_db|raw)/"; then
  echo "[FAIL] data/chroma_db 또는 data/raw 파일이 커밋에 포함됨"
  ERRORS=$((ERRORS + 1))
fi

# 3. prompt: 커밋에 코드 변경 혼합 확인
COMMIT_MSG_FILE=$(git rev-parse --git-dir)/COMMIT_EDITMSG
if [ -f "$COMMIT_MSG_FILE" ]; then
  MSG=$(head -1 "$COMMIT_MSG_FILE")
  if echo "$MSG" | grep -q "^prompt:"; then
    NON_PROMPT=$(git diff --cached --name-only | grep -vE "^prompts/|^docs/PROMPT_HISTORY")
    if [ -n "$NON_PROMPT" ]; then
      echo "[WARN] prompt: 커밋에 프롬프트 외 파일 포함: $NON_PROMPT"
      echo "  -> RULES.md: 프롬프트와 코드는 별도 커밋"
    fi
  fi
fi

# 4. API 키 하드코딩 검사
STAGED_PY=$(git diff --cached --name-only -- '*.py' '*.js' '*.jsx')
if [ -n "$STAGED_PY" ]; then
  if git diff --cached -- $STAGED_PY | grep -qiE "(api_key|apikey|secret)\s*=\s*['\"][^'\"]+['\"]"; then
    echo "[FAIL] 코드에 API 키가 하드코딩됨"
    ERRORS=$((ERRORS + 1))
  fi
fi

# 5. 파일 소유권 경고 (승구리 파일 수정 시)
SEUNGGURI_FILES="routers/training.py services/question_gen.py services/scorer.py components/training/"
for f in $SEUNGGURI_FILES; do
  if git diff --cached --name-only | grep -q "$f"; then
    echo "[WARN] 승구리 소유 파일 수정됨: $f — 합의 여부 확인 필요"
  fi
done

if [ $ERRORS -gt 0 ]; then
  echo "=== pre-commit 체크 실패 ($ERRORS건) ==="
  exit 1
fi

echo "=== pre-commit 체크 통과 ==="
exit 0
