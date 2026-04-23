# 테스트 체크리스트

> 개발 완료 후 반드시 실행. 실효성/위험성 양면 검토.
> `scripts/pre-commit-check.sh`가 커밋 시 자동 실행함.

---

## 실효성 테스트 (기능이 동작하는가)

### 백엔드 API

- [x] `POST /api/chat` — SSE 스트리밍 응답 정상 (sources → token → done) ✅ 2026-04-14
- [x] `POST /api/chat` — 편람 내 질문 시 confidence high/medium ✅ 2026-04-14 (top=0.87, "보통")
- [ ] `POST /api/chat` — 편람 외 질문 시 confidence low + 안내 메시지
- [ ] `POST /api/training/question` — 질문 생성 정상
- [ ] `POST /api/training/score` — 채점 응답 정상
- [ ] `/health` — 헬스체크 200 OK

### 프론트엔드

- [x] 챗봇 모드 전환 시 ChatScreen 렌더링 ✅ 2026-04-14
- [x] 질문 입력 → SSE 스트리밍 답변 실시간 표시 ✅ 2026-04-14
- [x] 출처 패널 + confidence 뱃지 표시 ✅ 2026-04-14
- [ ] 훈련 모드 전환 시 TrainingScreen 정상 동작 (기존 기능 회귀 없음)

### RAG 품질

- [ ] 검색 결과 상위 3건에 관련 문서 포함
- [ ] 가중치 [5:5, 4:6, 3:7] 비교 완료
- [ ] 할루시네이션 답변 없음 (편람 외 내용 생성 안 함)

---

## 위험성 테스트 (문제가 없는가)

### 보안

- [ ] `.env` 파일 커밋 안 됨 (.gitignore 확인)
- [ ] API 키 하드코딩 없음
- [ ] CORS 설정 localhost:3000 한정

### 안정성

- [ ] 빈 질문 전송 시 에러 처리
- [ ] ChromaDB 연결 실패 시 에러 메시지
- [ ] LLM API 타임아웃 시 에러 처리
- [ ] 동시 요청 시 서버 크래시 없음

### 협업 안전

- [ ] 승구리 소유 파일 무단 수정 없음
- [ ] 공통 파일 수정 시 핸드오프 로그 기록됨
- [ ] prompt: 커밋과 코드 커밋 분리됨

---

## 자동 테스트 스크립트

```bash
# 전체 테스트 실행
python -m pytest tests/ -v

# 백엔드 API 수동 테스트
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"계좌 개설 절차가 어떻게 되나요?"}'

# 헬스체크
curl http://localhost:8000/health
```
