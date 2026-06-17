# 다른 PC 시연 셋업 가이드

> 다른 자리/다른 사람도 **동일하게 시연**할 수 있게 하는 절차.
> 핵심: ChromaDB·`.env`는 git에 없으므로(고객 데이터 보호) **번들 zip으로 전달**하고,
> bge-m3 임베딩 모델은 묶지 않고 **시연 PC에서 설치 BAT이 자동 다운로드**한다.
>
> BAT 위치: [`scripts/demo/`](../scripts/demo/)
> - `1_시연번들_내보내기.bat` — **소스 PC**: `demo_bundle.zip` 생성
> - `2_시연_환경설정.bat` — **시연 PC**: 압축해제 + 설치(venv·패키지·모델·npm)까지. **최초 1회**
> - `3_시연_실행.bat` — **시연 PC**: 백엔드/프론트 기동 + 브라우저. **시연 때마다**

---

## 전체 흐름

```
[소스 PC]                          [USB/네트워크]          [시연 PC]
1_시연번들_내보내기.bat  ──>  demo_bundle.zip  ──>  git pull(main)
   (chroma_db + .env)                                 demo_bundle.zip 루트에 복사
                                                      2_시연_환경설정.bat  (최초 1회)
                                                      3_시연_실행.bat      (시연 때마다)
```

내 동작:
1. 내 PC에서 가끔 `1_시연번들_내보내기.bat` 실행 → `demo_bundle.zip` 나옴
2. 그 zip을 USB 등으로 시연 PC에 이동
3. 시연 PC에서 `git pull`(main) + zip을 **프로젝트 루트**에 복사
4. `2_시연_환경설정.bat` 실행(최초 1회 설치) → `3_시연_실행.bat` 실행(시연 때마다)

> ⚠️ `demo_bundle.zip` 에는 **`.env`(API 키)와 ChromaDB**가 들어있다. 외부 유출 금지.
> `.gitignore`로 커밋이 차단되어 있다.

---

## 소스 PC: 번들 내보내기

`scripts/demo/1_시연번들_내보내기.bat` 더블클릭.
- ChromaDB(`data/chroma_db`) + `.env` + `meta.db`를 모아 **`demo_bundle.zip`** 한 파일로 압축 (~수십 MB)
- **bge-m3 모델(2.2GB)은 묶지 않는다** — 시연 PC에서 설치 BAT이 자동 다운로드하므로 zip이 가볍다.

---

## 시연 PC: ① 환경설정 → ② 실행 (2단계 분리)

1. `git pull` (main 브랜치)
2. 받은 `demo_bundle.zip`을 **프로젝트 루트**(README.md 있는 곳)에 복사

### ① `scripts/demo/2_시연_환경설정.bat` — 최초 1회 (설치만)
- zip 압축 해제 → `data/chroma_db`, `.env` 배치
- `.venv` 생성 + 패키지 설치(torch CPU + requirements)
- **bge-m3 모델 자동 다운로드**(최초 1회, 인터넷 필요, ~2.2GB)
- `frontend/node_modules` 설치
- **서버는 띄우지 않고 종료** → 설치 끝.

### ② `scripts/demo/3_시연_실행.bat` — 시연 때마다 (기동만)
- 백엔드(8000) + 프론트(3000) 새 창으로 기동 + 브라우저 오픈
- `.venv`가 없으면 "먼저 환경설정 BAT 실행" 안내 후 종료.

> 환경설정(①)과 실행(②)을 나눈 이유 — 설치는 한 번이면 되고(수 분 소요),
> 시연은 ②만 눌러 **즉시** 띄울 수 있다. 모델도 ①에서 미리 받아 첫 질문이 빠르다.

### 사전 요구사항 (시연 PC에 미리 설치)
| 항목 | 비고 |
|------|------|
| Python 3.12 | python.org. "Add to PATH" 체크 |
| Node.js LTS | nodejs.org |
| Windows 10 1809+ | 내장 `tar.exe`로 zip 처리 (대부분 충족) |

---

## 모델 설치 명령어 (수동 참고)

BAT이 자동 실행하지만, 수동으로 할 때의 명령어:

```bat
:: 1) 가상환경
python -m venv .venv

:: 2) torch는 CPU 버전 권장 (용량/호환)
.venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cpu

:: 3) 나머지 의존성 (sentence-transformers 등)
.venv\Scripts\python -m pip install -r requirements.txt

:: 4) 프론트
cd frontend && npm install && cd ..
```

**bge-m3 임베딩 모델(약 2.2GB)** — `2_시연_환경설정.bat`이 설치 단계 `[4/5]`에서 자동 다운로드:

```bat
:: BAT이 내부적으로 실행하는 명령 (수동으로도 가능)
.venv\Scripts\python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"
```

- **인터넷 O**: 위 명령이 자동 다운로드 (캐시: `%USERPROFILE%\.cache\huggingface\hub\models--BAAI--bge-m3`). 이미 있으면 건너뜀.
- **인터넷 X(폐쇄망)**: 위 캐시 폴더를 인터넷 되는 PC에서 받아 같은 경로에 복사해 반입(실도입 단계 방식, [ONPREM_ROADMAP](ONPREM_ROADMAP.md) §5).

---

## 실행 (설치 후 매번)

환경설정(`2_시연_환경설정.bat`)은 **최초 1회만**. 이후 시연 때는 `3_시연_실행.bat`만 누르면 즉시 서버가 뜬다. (환경설정 BAT도 멱등이라 다시 눌러도 설치된 건 건너뛴다.)

---

## 트러블슈팅

| 증상 | 원인 / 해결 |
|------|-------------|
| `dimension 1024 != 3072` 또는 검색 에러 | `.env`에 `EMBEDDING_PROVIDER=local` 없음. 현재 DB는 bge-m3(1024). BAT은 백엔드를 local로 띄우지만, `.env`에도 박아두는 게 안전 ([TROUBLESHOOTING](TROUBLESHOOTING.md) 2026-06-16) |
| 검색 결과가 비어있음 | ChromaDB 미배치. `demo_bundle.zip`을 루트에 복사했는지, BAT [0/5]에서 "ChromaDB 배치" 떴는지 확인 |
| "AI 답변 생성 무료 한도" | Gemini 무료 생성 20회/일 소진. 키 교체 또는 다음날. 실도입은 로컬 생성 LLM([ONPREM_ROADMAP](ONPREM_ROADMAP.md)) |
| 첫 답변이 느림 | 정상 — bge-m3 최초 로딩. 두 번째부터 빠름 |
| `Windows tar 없음` | Windows 10 1809 미만. OS 업데이트 또는 수동 압축해제 |
| pip/npm 설치 실패 | 시연 PC 인터넷 차단. 폐쇄망이면 오프라인 wheel + 모델 캐시 사전 반입 필요 |

---

## BAT 수정 시 주의

BAT은 **CP949+CRLF**로 인코딩되어 있어 에디터로 직접 고치면 깨지기 쉽다.
내용을 바꿀 땐 [`scripts/demo/build_bats.py`](../scripts/demo/build_bats.py)를 수정한 뒤
`python build_bats.py`로 **재생성**할 것. (한글 출력 보존)

*Last Updated: 2026-06-16*
