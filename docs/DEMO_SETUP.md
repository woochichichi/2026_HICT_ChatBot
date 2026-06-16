# 다른 PC 시연 셋업 가이드

> 다른 자리/다른 사람도 **동일하게 시연**할 수 있게 하는 절차.
> 핵심: ChromaDB·`.env`·임베딩 모델은 git에 없으므로(고객 데이터 보호) **번들 zip으로 전달**한다.
>
> BAT 위치: [`scripts/demo/`](../scripts/demo/)
> - `1_시연번들_내보내기.bat` — **소스 PC**에서 실행 → `demo_bundle.zip` 생성
> - `2_시연_설치_및_실행.bat` — **시연 PC**에서 실행 → 압축해제 + 설치 + 서버 기동

---

## 전체 흐름

```
[소스 PC]                          [USB/네트워크]          [시연 PC]
1_시연번들_내보내기.bat  ──>  demo_bundle.zip  ──>  git pull
   (chroma_db+.env+모델)                              demo_bundle.zip 루트에 복사
                                                      2_시연_설치_및_실행.bat
                                                      브라우저 시연
```

내 동작 4단계:
1. 내 PC에서 가끔 `1_시연번들_내보내기.bat` 실행 → `demo_bundle.zip` 나옴
2. 그 zip을 USB 등으로 시연 PC에 이동
3. 시연 PC에서 `git pull` + zip을 **프로젝트 루트**에 복사 + `2_시연_설치_및_실행.bat` 실행
4. 브라우저(http://localhost:3000) 시연

> ⚠️ `demo_bundle.zip` 에는 **`.env`(API 키)와 ChromaDB**가 들어있다. 외부 유출 금지.
> `.gitignore`로 커밋이 차단되어 있다.

---

## 소스 PC: 번들 내보내기

`scripts/demo/1_시연번들_내보내기.bat` 더블클릭.
- ChromaDB(`data/chroma_db`) + `.env` + `meta.db`를 모아 **`demo_bundle.zip`** 한 파일로 압축
- **bge-m3 모델 캐시 포함 여부**를 물음:
  - 시연 PC에 **인터넷 있음** → `N` (첫 실행 시 모델 자동 다운로드, zip 작음 ~수십 MB)
  - 시연 PC가 **인터넷 없음(폐쇄망)** → `Y` (모델 ~2.2GB 포함, zip 커짐)

---

## 시연 PC: 설치 + 실행

1. `git pull` (이 저장소)
2. 받은 `demo_bundle.zip`을 **프로젝트 루트**(README.md 있는 곳)에 복사
3. `scripts/demo/2_시연_설치_및_실행.bat` 더블클릭

BAT가 자동으로:
- zip 압축 해제 → `data/chroma_db`, `.env`, (있으면) bge-m3 모델 캐시 배치
- `.venv` 생성 + 패키지 설치
- `frontend/node_modules` 설치
- 백엔드(8000) + 프론트(3000) 새 창으로 기동 + 브라우저 오픈

> 첫 질문은 bge-m3 로딩으로 **수십 초** 걸릴 수 있음(이후엔 빠름).

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

**bge-m3 임베딩 모델(약 2.2GB)** — 둘 중 하나:
- **인터넷 O**: 백엔드 첫 실행 시 `sentence-transformers`가 자동 다운로드
  (캐시 위치: `%USERPROFILE%\.cache\huggingface\hub\models--BAAI--bge-m3`)
- **인터넷 X(폐쇄망)**: 위 캐시 폴더를 소스 PC에서 복사해 같은 경로에 둠
  (내보내기 BAT에서 `Y` 선택 시 zip에 포함됨)

---

## 실행 (설치 후 매번)

`2_시연_설치_및_실행.bat`은 멱등 — `.venv`/`node_modules`가 이미 있으면 설치를 건너뛰고 바로 서버를 띄운다. 시연 때마다 같은 BAT을 다시 눌러도 됨.

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
