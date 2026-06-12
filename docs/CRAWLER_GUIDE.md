# 위키 크롤러 실행 가이드 (회사 PC)

> api-spec.md 섹션 9의 운영 절차. 사내 위키(wiki.hanwhawm.com) BM001 공간을
> 자동 수집해 ChromaDB에 증분 적재한다.

## 실행 방식 선택

| 회사 PC 환경 | 방식 | 산출물 |
|--------------|------|--------|
| Python 있음 | A. `sync_manual.py --source crawl` (아래 1~5번) | ChromaDB 직접 적재 |
| **Python 없음/설치 불가** | **B. `wiki_fetch.ps1` (PowerShell 내장)** | HTML 폴더 → Python PC로 옮겨 `--source dir` 적재 |

> 방식 B는 Windows 내장 PowerShell만 사용 — 설치/관리자권한/신규 바이너리 0.
> 상세는 맨 아래 "방식 B" 섹션 참조. 아래 1~5번은 방식 A(Python) 기준.

## 0. 준비 (최초 1회) — 폐쇄망 zip 반입 방식

> 회사에서 git/PyPI 접속이 안 되므로 zip 2개를 반입한다:
> `hict_chatbot_feature-wiki-ingest_*.zip` (코드), `hict_wheels_*.zip` (의존성 휠)

```bash
# 1. 코드 zip을 기존 프로젝트 폴더에 덮어쓰기 풀기
#    (.env / data / chroma_db는 zip에 없으므로 기존 것 그대로 유지됨)

# 2. 의존성 오프라인 설치 — 인터넷 불필요 (휠 폴더에서 직접 설치)
#    wheels zip을 임의 폴더(예: C:\wheels)에 풀고:
pip install --no-index --find-links C:\wheels beautifulsoup4 rank_bm25 httpx

# 3. 설치 확인
python -c "import bs4, rank_bm25, httpx; print('ok')"
```

> 신규 의존성은 3개뿐 (beautifulsoup4, rank_bm25, httpx) — 전부 순수 파이썬이라
> 파이썬 버전 무관. numpy는 chromadb와 함께 이미 설치되어 있음.
> 휠 zip의 numpy는 py3.12/win64용 예비 — 기존에 numpy 있으면 무시해도 됨.

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

---

## 방식 B: PowerShell 조회 (Python 없는 회사 PC)

Windows 내장 PowerShell만 사용. 설치·관리자권한·신규 바이너리 0.
회사 PC에서는 HTML만 수집하고, 적재(파싱→임베딩→ChromaDB)는 Python 있는 PC에서 한다.

### B-1. 회사 PC에서 HTML 수집

반입 파일: `scripts/wiki_fetch.ps1`, `scripts/wiki_fetch.config.txt` (코드 zip에 포함)

```
# 1. 설정 확인 — scripts\wiki_fetch.config.txt 의 BASE_URL/SPACE_KEY/URL 템플릿
#    (기본값이 wiki.hanwhawm.com / BM001 로 채워져 있음)

# 2. auth header 값 준비 (셋 중 하나)
#    - 실행 시 프롬프트에 붙여넣기 (가장 간단)
#    - scripts\wiki_auth.txt 에 저장 (gitignore됨)
#    - -AuthValue "..." 파라미터

#    값 얻는 법: 브라우저 로그인 → F12 → Network 탭 → 아무 위키 요청 클릭
#    → Request Headers 의 Cookie: 값 전체 복사

# 3. 연결 테스트 겸 전체 수집
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\wiki_fetch.ps1

#    → "rootPageId=23069356 -> walking full tree" 로그 확인
#    → page_<id>.html 들이 scripts\wiki_html\ 에 저장됨
#    → "auth header rejected" 나오면 쿠키 다시 복사

# 매일 변경분만 (최근 업데이트 화면)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\wiki_fetch.ps1 -Incremental
```

> 사내 인증서 오류 시: 회사 CA가 Windows 신뢰저장소에 있으면 자동 통과됨.
> 그래도 막히면 `-SkipCertCheck` (단, 신뢰 가능한 내부망에서만).

### B-2. 수집한 HTML을 Python PC로 옮겨 적재

`scripts\wiki_html\` 폴더를 Python 있는 PC로 복사 후:

```bash
python scripts/sync_manual.py --source dir --path scripts/wiki_html/
```

이후는 방식 A와 동일 (diff 적재 → ChromaDB). 정확도 측정도 동일하게 `test_accuracy.py`.

### 방식 B 문제 해결

| 증상 | 대응 |
|------|------|
| `auth header rejected` | 쿠키 만료 — 브라우저에서 재복사 |
| `rootPageId not found` 경고 | config의 `ROOT_PAGE_ID=23069356` 직접 지정 |
| 인증서 오류 | `-SkipCertCheck` (내부망 한정) |
| 0 page(s) to fetch | URL 템플릿이 실제 화면과 다름 — config의 LIST_PATH/TREE_PATH 수정 |
