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
