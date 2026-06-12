# 시행착오 로그

> AI(Claude/Cursor)와 개발자가 겪은 에러, 원인, 해결책을 기록.
> 같은 실수를 반복하지 않기 위한 참조 문서.

---

## 작성 규칙

```
### YYYY-MM-DD | 에러 한줄 요약
- **증상**: 무엇이 발생했는지
- **원인**: 왜 발생했는지
- **해결**: 어떻게 고쳤는지
- **교훈**: 다음에 주의할 점
```

---

## 2026-06-12 | Gemini 임베딩 일일 한도(1000/일)로 대량 적재 중단

- **증상**: 50페이지(1281청크) 적재 중 489청크에서 `429 ... EmbedContentRequestsPerDayPerUserPerProjectPerModel-FreeTier, quotaValue: 1000`로 중단
- **원인**: 무료 티어는 분당 100 외에 **일일 1000회** 임베딩 한도가 별도로 있음. 청크당 2회(제목+내용)라 ~500청크면 일일 소진
- **해결**: 일일 리셋(PT 자정) 후 재실행 — diff가 이미 적재분을 스킵하므로 이어서 진행됨. 근본 해결은 로컬 임베딩(bge-m3) 전환(폐쇄망 실도입 정답, 한도 없음)
- **교훈**: 무료 티어로는 수백 페이지 규모 적재가 하루에 안 끝남. 실데이터 규모(520p=14299청크)는 반드시 로컬 임베딩 필요. 측정·데모는 부분 적재로도 가능

## 2026-06-12 | 출처가 파일명(page_<id>)으로 표시 — dir 커넥터가 제목 덮어씀

- **증상**: 챗봇 출처 패널에 페이지 제목 대신 `page_23069748` 같은 파일명이 표시
- **원인**: `LocalHtmlConnector`가 `RawDocument.title = p.stem`(파일명)을 전달 → `parse_html`이 "title이 이미 있으면 <title> 추출 스킵" 로직이라 파일명이 그대로 제목으로 굳음
- **해결**: 커넥터가 `title=None` 전달 → 파서가 HTML `<title>`에서 실제 제목("2) 고객번호") 추출. 기존 적재분은 `backfill_source_url.py`로 메타데이터만 보정(재임베딩 X)
- **교훈**: 파서에 "값 있으면 스킵" 폴백을 둘 때, 호출자가 무의미한 기본값(파일명)을 넘기면 폴백이 안 먹음. 커넥터는 모르는 값은 None으로 넘겨 파서가 추출하게 할 것

## 2026-06-12 | 폐쇄망 회사 PC에 Python/pip 없음 → PowerShell 수집으로 분리

- **증상**: 회사 PC에 Python·pip 미설치, 설치도 불가(폐쇄망 + 보안정책). `sync_manual.py --source crawl`(Python) 실행 자체가 불가능
- **원인**: 수집(내부망 접근 필요)과 적재(파싱/임베딩/ChromaDB)를 한 머신에서 한다고 가정. 실제로는 "내부망에서 HTML을 꺼내는 일"만 회사 PC에서 필요하고 나머지는 어디서든 가능
- **해결**: 작업을 2단계로 분리 — ① 회사 PC: **Windows 내장 PowerShell**(`Invoke-WebRequest`)로 HTML만 수집 → ② Python PC(집): 기존 `--source dir` 커넥터가 그 HTML 폴더를 그대로 적재. PowerShell은 모든 Windows에 내장이라 설치 0
- **교훈**: 폐쇄망 제약은 "전부 한 머신"이 아니라 "내부망 접근이 꼭 필요한 최소 단계"만 분리하면 풀린다. 신규 바이너리/설치가 보안 검토 대상이면 OS 내장 도구(PowerShell)가 정치적으로도 유리

## 2026-06-12 | PowerShell `$PSScriptRoot`가 param 기본값에서 비어 config 못 찾음

- **증상**: `.bat`로 `wiki_fetch.ps1` 실행 시 `config file not found: \wiki_fetch.config.txt` (경로 앞이 `\`로 시작 = 폴더 부분이 빈 문자열). 스크립트 옆에 config가 있는데도 못 찾음
- **원인**: `param([string]$ConfigPath = "$PSScriptRoot\...")` — Windows PowerShell 5.1에서 `$PSScriptRoot`는 **param 바인딩 시점에 아직 안 채워져** 빈 문자열로 평가됨. 본문에서는 정상이지만 param 기본값에서는 비어 경로가 드라이브 루트로 잡힘
- **해결**: param 기본값에서 `$PSScriptRoot` 사용 금지. 본문에서 `$PSScriptRoot` → `$MyInvocation.MyCommand.Definition` → `Get-Location` 순으로 폴백해 `$scriptDir`를 구한 뒤 config/출력경로 해석. config 없으면 throw 대신 내장 기본값 사용
- **교훈**: PS 스크립트 폴더 경로는 항상 본문에서 다중 폴백으로 구할 것. 상대 출력경로는 cwd가 아닌 스크립트 폴더 기준으로(관리자 실행 시 cwd=System32라 파일이 엉뚱한 곳에 생김)

## 2026-06-12 | Confluence 로그인 오탐 — 정상 페이지를 'auth rejected'로 판정

- **증상**: 유효한 인증인데도 모든 페이지에서 `auth header rejected (bounced to login page)` 발생
- **원인**: "본문에 `os_username`/`loginform` 문자열이 있으면 로그인 페이지로 튕긴 것"으로 판정. 그러나 **로그인된 Confluence 페이지에도 우측 상단 로그인 드롭다운(숨은 로그인 폼)이 있어** `os_username`이 항상 존재 → 매 페이지 거짓 양성
- **해결**: 본문 문자열 스캔 제거. 인증 실패의 신뢰 가능한 신호는 **최종 URL이 `login.action`으로 리다이렉트되는 것**뿐 → 그것만으로 만료 판정
- **교훈**: 인증 만료 감지는 "본문에 로그인 관련 단어 있나"가 아니라 "로그인 페이지로 리다이렉트됐나"(최종 URL)로 판단. 정상 페이지의 헤더/푸터에 인증 관련 마크업이 흔히 들어있음

## 2026-06-12 | 사내 위키는 Windows 통합인증으로 통과 (쿠키 불필요)

- **증상**: F12에서 쿠키를 수동으로 골라 복사하는 절차가 번거롭고 오류가 잦음 (`dt*`=Dynatrace 모니터링 쿠키를 인증용으로 착각 등)
- **원인**: 인증 방식을 "세션 쿠키"로만 가정. 실제 사내 위키(wiki.hanwhawm.com)는 도메인 PC의 Windows 세션을 신뢰
- **해결**: `Invoke-WebRequest -UseDefaultCredentials`로 **쿠키 없이** 통과 확인 (`rootId: True`, `login.action` 리다이렉트 없음, len 60051). `wiki_fetch.ps1 -WindowsAuth` 모드 추가. 쿠키가 필요한 환경 대비로 "Copy as cURL/헤더블록/원시값"에서 쿠키를 자동 추출하는 `Extract-Cookie`도 추가(`Read-Host`는 멀티라인 붙여넣기 불가 → 파일 입력 권장)
- **교훈**: 사내 인트라넷은 쿠키보다 Windows 통합인증(NTLM/Kerberos)이 되는 경우가 많음 → 쿠키 작업 전에 `-UseDefaultCredentials`부터 시도. 인증 입력은 사용자에게 형식을 강요하지 말고(어느 복사 방식이든) 자동 파싱

## 2026-04-14 | pip install 한국어 주석 인코딩 에러

- **증상**: `pip install -r requirements.txt` 실행 시 `UnicodeDecodeError: 'cp949'`
- **원인**: Windows cp949 환경에서 requirements.txt 내 한국어 주석을 파싱 못 함
- **해결**: `PYTHONUTF8=1` 환경변수 설정 후 실행, 또는 핵심 패키지만 개별 설치
- **교훈**: Windows에서 한국어 주석 포함된 txt 파일은 UTF-8 인코딩 명시 필요

## 2026-04-14 | google-genai ImportError

- **증상**: `from google import genai` 에서 `ImportError: cannot import name 'genai'`
- **원인**: `google-genai` 패키지 미설치 (pip install 실패로 누락)
- **해결**: `pip install "google-genai>=1.0.0"` 개별 설치
- **교훈**: requirements.txt 전체 설치 실패 시 핵심 패키지 개별 설치로 우회

## 2026-06-11 | kiwipiepy 한글 사용자명 경로에서 모델 로딩 실패 + 세그폴트

- **증상**: `Kiwi()` 초기화 시 `Exception: Cannot open extract.mdl for WordDetector` 발생 후 인터프리터 종료 시 Segmentation fault. pytest에서는 실패 리포트 생성 중 Kiwi 객체 `repr()` 호출 → access violation으로 pytest 자체가 크래시
- **원인**: kiwipiepy 네이티브 라이브러리가 비ASCII 경로(한글 사용자명 `C:\Users\전우형\...`)의 모델 파일을 열지 못함. venv가 한글 경로 아래 있으면 발생
- **해결**: kiwipiepy 의존성 제거 → 한국어 **문자 bigram 토크나이저**로 교체 (`backend/services/keyword_index.py`). bigram은 조사 변형("고객번호는"↔"고객번호")을 자연 매칭하고 순수 파이썬이라 폐쇄망·한글 경로 무관
- **교훈**: 네이티브 확장 패키지는 Windows 한글 사용자명 환경에서 경로 인코딩 문제 빈발. 회사 PC도 한글 계정명이므로 같은 문제 예상 — 도입 전 비ASCII 경로 테스트 필수. 세그폴트 나는 라이브러리는 uvicorn 서버 프로세스에 절대 싣지 말 것

## 2026-06-11 | Gemini 임베딩 무료 티어 분당 한도(429 RESOURCE_EXHAUSTED)

- **증상**: 인제스트 중 `429 RESOURCE_EXHAUSTED ... embed_content_free_tier_requests, limit: 100` 발생
- **원인**: 무료 티어 임베딩 분당 100건 제한 — **배치 호출이라도 배치 내 텍스트가 개별 카운트**됨 (100건 배치 1회 = 분당 한도 전부 소진)
- **해결**: `EMBED_BATCH_SIZE` 100→90 축소 + `embed_in_batches()`에 429 감지 시 지수 백오프(30s→60s→120s, 최대 5회) 재시도 추가
- **교훈**: 일일 한도(1,000건)도 있음 — 대량 적재가 중단되면 다음날 같은 명령 재실행 (diff가 완료분을 스킵하므로 이어서 진행됨)

## 2026-05-08 | Gemini API 호출 시 SSL CERTIFICATE_VERIFY_FAILED (사내 SSL 인터셉트)

- **증상**: `/api/training/score` 호출 시 `httpx.ConnectError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate in certificate chain`
- **원인**: 사내 프록시(Zscaler 등)가 Google API HTTPS 트래픽에 자체 서명 CA를 끼워 넣음 → `google-genai` SDK 내부의 `httpx`가 `certifi` 기본 CA만 사용해 검증 실패
- **해결**:
  1. `powershell scripts/extract-ca-bundle.ps1 -OutPath C:\Users\<user>\company-ca.pem` 으로 Windows 신뢰 저장소(LocalMachine/Root,CA + CurrentUser/Root,CA)에서 CA 일괄 추출
  2. `.env`에 `SSL_CERT_FILE=C:\Users\<user>\company-ca.pem` 추가
  3. `backend/config.py`에서 `REQUESTS_CA_BUNDLE`/`CURL_CA_BUNDLE`도 함께 동기화 (requests/urllib 사용 라이브러리 대비)
- **검증**: `ssl.create_default_context(cafile=...)` + `httpx.get('https://generativelanguage.googleapis.com/')` 핸드셰이크 성공(404 응답은 정상)
- **교훈**:
  - `httpx`는 표준과 달리 `SSL_CERT_FILE`을 자동 인식하지 않음. 단, `google-genai` SDK는 `_api_client._ensure_httpx_ssl_ctx`에서 명시적으로 환경변수를 읽어 SSL context를 만든다
  - `verify=False`는 절대 금지 (사내 보안 정책 위반 + 중간자 공격 노출). 반드시 사내 CA를 신뢰 목록에 추가하는 방식으로 해결할 것
  - venv 재생성/PC 교체 시 PEM이 사라지므로 `extract-ca-bundle.ps1` 재실행 필요
