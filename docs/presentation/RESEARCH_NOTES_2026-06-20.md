# PoC 발표 근거 리서치 노트 (2026-06-20)

> 30분 PoC 발표자료(.pptx)의 "데이터 허브 비전" + "LLM 한계와 해결방향" 슬라이드 근거.
> 웹 리서치(병렬 8검색 + 2종합) 결과. 각 사실은 출처 URL과 함께. ⚠️ 표시는 재확인 필요.
> 생성: `make_ppt_hanwha_poc.py` 가 이 노트의 사실을 인용.

---

## A. 데이터 허브 — 비정형 데이터를 답변 DB로

### 트렌드 (왜 지금인가)
- 금융사 지식은 메일·메신저·엑셀 메모·회의록·위키 등 "검색 안 되는 비정형 데이터"에 흩어져 있음.
- 2024~2026 글로벌·일본·한국 금융사가 이를 RAG 기반 "출처 달린 답변 DB"로 통합 중.
- 동력 3가지: ① 측정 가능한 시간절감 ② 규제·보안(망분리) 충족 ③ 출처 인용으로 신뢰성.

### 사례 (출처 포함)
**일본 금융**
- **SMBC(미쓰이스미토모FG)** — 사내 AI 'SMBC-GAI'에 RAG, 사내 규정·통達·매뉴얼 약 **130만 건** 인덱싱 횡단검색 + 참조자료 병기. https://dx-consultant.co.jp/rag_case/
- **미즈호증권** — 사무수속서 RAG 'MOAI 서치' 사용자테스트 **해결률 ~96% / 재사용의향 ~98%**; Claude 기반 회의록 에이전트 1인 월 4h+ 절감. https://www.mizuho-fg.co.jp/dx/articles/ai-poc-interview/index.html
- **일본생명** — 보험약관·운용매뉴얼 Claude RAG **유효답변 ~90%(목표 97%)**, 엑셀 병합셀까지 판독, 콜센터 응대 목표. https://news.mynavi.jp/techplus/article/20250901-3421256/
- **MUFG** — 사내 AI 'AI-bow' 2024년 **월 22만 시간 절감** 보고. https://www.mufg.jp/profile/strategy/dx/articles/0133/index.html

**한국 금융/증권**
- **신한투자증권** — 사내 AI '챗프로', 스켈터랩스 RAG, **온프레미스(망분리)**. ⚠️ "15,000건/30분단축/MOS 5%+" 정량치는 1차 기사 미확인. https://byline.network/2024/11/26-379/
- **미래에셋증권** — 직원이 매뉴얼 업로드해 전용 챗봇 생성(노코드 'AI 어시스턴트'), **온프레미스 sLLM 하이퍼클로바X HCX-DASH**(네이버클라우드 첫 구축형). https://www.financialpost.co.kr/news/articleView.html?idxno=213221
- **키움증권** — 인포뱅크 LLM RAG 'AI 업무상담 챗봇'(2025-10), 내부문서 실시간 탐색 + 1차 응대 후 상담원 핸드오프. https://www.etnews.com/20251031000139

**글로벌 제품(참조 아키텍처)**
- **Amazon Q Business** — SharePoint·OneDrive·Teams·Gmail·Exchange·Slack + ACL을 단일 인덱스로, 문장단위 출처인용 + 실시간 환각보정. https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/connectors-list.html

### 비정형→답변DB 기술 파이프라인
1. **파싱**: 디지털PDF 네이티브 / 스캔·필기 OCR 자동 라우팅, 병합셀·표는 구조 추출(Docling). https://procycons.com/en/blogs/pdf-data-extraction-benchmark/
2. **정규화/청킹**: 재귀청킹(~512토큰, 오버랩 100~200)이 2025~26 벤치마크상 충분. https://www.firecrawl.dev/blog/best-chunking-strategies-rag
3. **메타데이터 보강**: 요약·키워드·엔티티 부착 + Anthropic Contextual Retrieval로 검색실패 **최대 67%↓**. https://platform.claude.com/cookbook/capabilities-contextual-embeddings-guide
4. **중복제거**: 동일·유사 문서 제거(Databricks). 반복 등장 시에만 KB화(fin.ai). https://docs.databricks.com/gcp/en/generative-ai/tutorials/ai-cookbook/quality-data-pipeline-rag
5. **PII 비식별**: 적재 전 주민·계좌·연락처 마스킹(Microsoft Presidio, 한국어 인식기 별도검증). https://github.com/microsoft/presidio
6. **ACL 보존**: 임베딩 단계에서 원본 접근권한 보존(권한경계 유출 방지) — 증권사 PoC 최난제.

### 우리 로드맵 함의
- 현재: 업무편람(정형) 단일소스 RAG = 글로벌·국내 검증된 "출처 인용형 답변DB" 기본형.
- 향후: 메일·메신저·엑셀·회의록을 ACL보존+PII마스킹으로 통합하는 **개인별 비정형 데이터 허브**.

---

## B. LLM 한계와 해결방향

### 한계 1. 환각
- 원인: LLM 학습이 '자신있는 추측'에 보상(OpenAI). https://openai.com/index/why-language-models-hallucinate/
- 해결 4단계: ①그라운딩(Vertex high-fidelity / Azure On Your Data) ②출처표기(Galileo Chunk Attribution) ③사후검증(Azure Groundedness, Bedrock, NeMo Guardrails self_check_facts) ④거부/기권(Cleanlab TLM).
- 현실: RAG 환각 **70~90%↓ 하지만 잔존 17~33%**(스탠퍼드 법률RAG) → 신뢰도 게이트 + 고위험 상담원 검토. https://www.sphereinc.com/blogs/best-enterprise-rag-platforms-2026
- 우리: bge-m3 + confidence 재보정 + 출처중복제거 + 저신뢰 폴백. 향후 RAGAS Faithfulness CI, BGE Reranker v2(+15%p).

### 한계 2. 최신성(컷오프)
- 해결: 재학습이 아니라 **RAG + 증분 재인덱싱**(문서 변경 이벤트 트리거). https://towardsdatascience.com/grounding-your-llm-a-practical-guide-to-rag-for-enterprise-knowledge-bases/
- 2025 트렌드 **Agentic RAG**(ReAct/Self-Ask/Search-o1): 모델이 언제·어떻게 검색할지 결정, 시세/공시는 도구호출. https://arxiv.org/abs/2501.09136
- 우리: 내부문서 RAG로 재학습 없이 최신성. 향후 변경트리거 증분 재인덱싱 → Agentic + 시세 도구.

### 한계 3. 도메인 정확도 (RAG vs 파인튜닝 vs 가드레일)
- 역할분담: RAG=오픈북(최신성·출처·환각↓), 파인튜닝=클로즈드북(포맷·수치추론), 가드레일=감독관(이탈·PII 차단). https://www.redhat.com/en/topics/ai/rag-vs-fine-tuning
- 정량: 멀티에이전트 RAG **FinanceBench 56% vs GPT-4 단순 19%**(검색설계 > 모델). https://intuitionlabs.ai/articles/llm-financial-document-analysis
- BloombergGPT(50B 금융전용)도 ConvFinQA 43% < GPT-4 zero-shot 69~76% → from-scratch 비권장.
- 우리: RAG 우선, 향후 LoRA로 응대 포맷·톤 보정 검토.

### 한계 4. 보안·규제·망분리 (한국 특유 최대 변수)
- 규제: 금융위 **'망분리 개선 로드맵'(2024-08)**, 신청기간 **74개사 141건** 혁신금융 특례. https://www.fsc.go.kr/po010101/83554
- 모델 선택지: HyperCLOVA X(미래에셋 온프레미스), **EXAONE/Llama/Qwen**(LG CNS 금융 AI 평가도구 29지표·1200문항), 카카오뱅크 **Qwen3-30B-A3B** 채택(2025 금융AI챌린지), Upstage **Solar**+신한DS.
- 거버넌스: 휴먼인더루프 → governance-in-the-loop, 감사로그/추적성, 모델 캐스케이딩(소형→대형).
- 우리: 폐쇄망 이식형 아키텍처(ChromaDB 폴더복사), LLM만 교체(Qwen3/HyperCLOVA X/Solar 후보), 출처 추적성.

⚠️ 모든 정확도·시간절감 수치는 벤더/회사 자체 발표값 — 한국 증권사 코퍼스 전이 시 실측 검증 필요.
