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
