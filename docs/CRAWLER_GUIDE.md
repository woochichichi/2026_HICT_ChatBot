# 위키 크롤러 실행 가이드 (회사 PC)

> api-spec.md 섹션 9의 운영 절차. 사내 위키(wiki.hanwhawm.com) BM001 공간을
> 자동 수집해 ChromaDB에 증분 적재한다.

## 0. 준비 (최초 1회)

```bash
git pull
git checkout feature/wiki-ingest    # 머지 전이면 이 브랜치 사용

pip install -r requirements.txt     # beautifulsoup4, httpx 추가됨
# 실패 시 (사내망 인코딩): PYTHONUTF8=1 설정 후 재시도 — TROUBLESHOOTING.md 참조
```

## 1. .env 설정

기존 `GOOGLE_API_KEY`(+ 사내망이면 `SSL_CERT_FILE`)에 아래 3개 추가:

```
WIKI_BASE_URL=https://wiki.hanwhawm.com
WIKI_SPACE_KEYS=BM001
WIKI_COOKIE=<아래 방법으로 복사>
```

**쿠키 복사 방법** (세션 만료 시마다 갱신 필요):

1. 브라우저로 위키 로그인 → F12(개발자도구) → **Network 탭**
2. 위키 아무 페이지나 새로고침 → 목록 첫 요청 클릭
3. **Request Headers → `Cookie:`** 값 전체 복사
4. `.env`의 `WIKI_COOKIE=` 뒤에 붙여넣기 (따옴표 없이 그대로)

> 사내 위키가 https인데 인증서 오류가 나면:
> `powershell scripts/extract-ca-bundle.ps1 -OutPath C:\Users\<계정>\company-ca.pem`
> 후 `.env`에 `SSL_CERT_FILE=C:\Users\<계정>\company-ca.pem` (TROUBLESHOOTING.md 2026-05-08)

## 2. 연결 테스트 (안전 — 적재/임베딩 없음)

```bash
python scripts/sync_manual.py --source crawl --dry-run
```

확인할 것:

- `페이지 트리 발견: rootPageId=23069356 — 전체 트리 순회` 로그가 나오는지
- `→ 페이지 N건` — **전체 페이지 수 확인** (적재 시간 추정용)
- `세션 만료로 추정` 에러가 나오면 → 쿠키 다시 복사

## 3. 본 적재

```bash
python scripts/sync_manual.py --source crawl
```

- 완료 리포트: `문서 N건 중 M건 변경 | 청크 +a / -b | 임베딩 c건`
- **Gemini 무료 티어 한도**: 분당 100건(자동 대기·재시도 내장), **일일 1,000건**.
  페이지가 많아 일일 한도에 걸려 중단되면 → **다음날 같은 명령 재실행**.
  이미 적재된 문서는 hash 스킵되므로 이어서 진행됨 (diff 설계의 이점)

## 4. 매일 배치 (변경분만)

"최근 업데이트" 화면의 실제 URL을 확인해 `.env`에 설정:

```
WIKI_RECENT_URL={base}/pages/recentlyupdated.action?key={space}
```

> 기본값이 안 맞으면 브라우저에서 해당 화면 URL을 복사해 `{base}`/`{space}` 자리만 치환.

```bash
python scripts/sync_manual.py --source crawl --incremental
```

Windows 작업 스케줄러 등록 (매일 08:30 예시):

```
schtasks /create /tn "wiki-sync" /sc daily /st 08:30 ^
  /tr "cmd /c cd /d C:\<프로젝트경로> && .venv\Scripts\python.exe scripts\sync_manual.py --source crawl --incremental"
```

## 5. 적재 확인 + 정확도 측정

```bash
# 컬렉션 청크 수 확인
python -c "import sys; sys.path.insert(0,'.'); from backend.services.rag import get_chroma_client; c=get_chroma_client(); print(c.get_collection('faq_contents').count())"

# 검색 정확도 측정 (tests/test_questions.json 기반)
python scripts/test_accuracy.py --tag company-baseline
```

## 문제 발생 시

| 증상 | 대응 |
|------|------|
| `SessionExpiredError` | 쿠키 재복사 (1번 절차) |
| SSL 인증서 오류 | extract-ca-bundle.ps1 → SSL_CERT_FILE 설정 |
| 429 한도 초과 반복 | 자동 재시도 됨. 일일 한도면 다음날 재실행 |
| 페이지 트리 없음 폴백 경고 | `WIKI_PAGE_LIST_URL` 템플릿이 실제 목록 화면 URL과 다름 — 실제 URL로 수정 |
| 그 외 에러 | docs/TROUBLESHOOTING.md 확인 후 기록 |
