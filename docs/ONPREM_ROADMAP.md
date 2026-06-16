# 온프레미스(폐쇄망) 실도입 로드맵 — 벤치마크 · 모델 선택지 · 운영 애로 대응

> README 4주차 산출물(온프레미스 로드맵)의 근거 문서. 2026-06-16 시장 조사 기반.
> 목적: 한화투자증권 폐쇄망(망분리) 환경에 챗봇/훈련 모드를 실도입할 때
> "어떤 모델로 / 어떻게 / 무엇을 조심하며" 가는지를 외부 레퍼런스로 뒷받침.
>
> 관련: [api-spec.md](api-spec.md) 섹션 4(LLM 추상화)·10(Hybrid) · [ANSWER_QUALITY.md](ANSWER_QUALITY.md)

---

## 0. 한 줄 요약

현재 우리 스택(**bge-m3 로컬 임베딩 + 하이브리드(BM25+벡터) 검색 + RAG + 출처표시**)은
글로벌 "소버린 AI" 표준 아키텍처와 **거의 일치**한다. 남은 변수는 **(1) 생성 LLM 선택**,
**(2) 망분리 규제 대응**, **(3) GPU 사이징/운영**뿐. 아키텍처를 새로 갈아엎을 필요 없음.

> 외부 컨설팅이 정의한 표준 폐쇄망 스택 = "vLLM/TGI + 오픈웨이트(Llama/Mistral/Qwen/DeepSeek)
> + 로컬 임베딩(**nomic-embed 또는 BGE-M3**) + **dense+BM25 하이브리드 + 리랭킹** + egress 차단"
> → 우리 구성과 판박이. (출처: MindMap Sovereign AI)

---

## 1. 핵심 전제 — 폐쇄망에서는 프론티어 API 불가

GPT·Claude·Gemini 등 **외부 호스팅 모델은 호출 자체가 망 위반**이라 폐쇄망에서 구조적으로 못 씀.
규제 산업의 실도입은 **전부 오픈웨이트(또는 국산 벤더) 자체 호스팅**이다.
- 규제 동인(글로벌): EU AI Act, GDPR 데이터 residency, SR 11-7(은행 모델리스크), NYDFS Part 500, FFIEC
- 규제 동인(국내): **망분리(網分離) 제도** — 한국 특유의 최대 변수(§4 참조)

---

## 2. 글로벌 레퍼런스 — 누가 어떤 모델로 효과를 보나

| 기관 | 모델 / 방식 | 효과 |
|------|------------|------|
| HSBC | Mistral AI 자체 호스팅(다년 전략 제휴) | 고객 커뮤니케이션·재무분석·번역 |
| BNP Paribas | Mistral 온프레미스 | 고객지원·영업·IT, 규제준수 |
| DBS은행(싱가포르) | 자체 GenAI 코파일럿(CSO Assistant) | 상담원 500명, 실시간 전사, 응대시간 -20% |
| 일본 대형 금융그룹(Yodo Labs) | **Qwen + LoRA**, Triton+vLLM, H100 | GDPR 대응 100% 온프레미스 |
| 미군 의료센터 | **Llama 3.2 11B**(A100 40GB 1장) → 복잡건 3.3 70B | 보호의료정보(PHI) 처리 |
| Los Alamos(LANL) | 자체 호스팅(2025.01) | CUI·UCNI·ITAR 데이터 |

**주력 오픈웨이트 모델군**: Llama 3.x, Mistral/Mixtral, Qwen 2.5/3, Gemma 2, DeepSeek V3, Phi-3.
오픈웨이트 성능 격차가 좁혀짐(Llama 3.3 70B·Qwen 2.5 72B·DeepSeek V3가 GPT-4급 평가의 한 자릿수 %p 이내),
**엔터프라이즈 볼륨에선 온프레미스 분할상각 단가 < 클라우드 토큰 단가**로 경제성도 역전.

---

## 3. 한국 금융·증권권 레퍼런스 (가장 직접적) ⭐

> 우리와 똑같은 "증권사 + 망분리 + RAG" 조합이 이미 다수 운영/구축 중. 두 갈래.

### (A) 국산 벤더 특화 LLM을 온프레미스로 — 국내 금융권 주류

| 기관 | 파트너 / 모델 | 특징 (우리와의 접점) |
|------|--------------|----------------------|
| **한국투자증권** | 크라우드웍스(2025.08) | **RAG 기반 + 금융 보안·규제·망분리 대응**, 문서요약·분석 — 우리 PoC와 목표 동일 |
| **IBK투자증권** | 핑거 + 원라인에이아이 | 온프레미스, **증권 특화 LLM 'OLA-F'**(법규·용어·수치추론) + RAG + STT + DRM/SSO/PII필터 |
| **케이뱅크** | KT·KT클라우드·업스테이지 | 인뱅 최초 프라이빗 LLM, 금융데이터 post-training, 금융자격시험 23종 평가 |
| **신한투자증권** | — | 금융투자 특화 온프레미스 AI |
| **우리투자증권** | 올거나이즈 | 외부망 물리분리 온프레미스 금융특화 플랫폼 |
| **하나은행 (H-GPT)** | 하나금융티아이(자체) | **"AI모드/검색모드" + 규정·FAQ RAG + 출처 제공** — 우리 챗봇 UX와 사실상 동일 |
| **한국은행 (BOKI)** | 네이버클라우드(HyperCLOVA X, NeuroCloud) | **완전 폐쇄망 온프레미스**, 내부문서 140만 건, 중앙은행 세계 최초 소버린 AI |

### (B) 정부 지원

금융당국이 **"금융권 AI 플랫폼"**을 구축해 **전문가가 선정한 오픈소스 모델을 내부망에 바로 설치**할 수 있도록 지원(2025 상반기).

### 국산 vs 글로벌 — 의미

- 국내 금융권은 **국산 금융특화 LLM**(업스테이지 Solar, 원라인 OLA-F, 네이버 HyperCLOVA X) 채택이 두드러짐.
- README 후보 **Qwen3는 글로벌 오픈웨이트 경로**. → **PoC 비교 테스트 대상에 국산 금융특화 모델도 포함** 권장.

---

## 4. ⚠️ 망분리 규제 — 한국 특유의 최대 애로

- 한은 총재 공개 발언: **"AI 활용과 망분리 제도는 더 이상 공존 불가, 근본 개선 필요."**
- **BOKI조차 망분리 사업·예산 미완으로 서비스 범위가 제한**된 채 운영 중(예산 배정 후 확대 예정).
- → 한화투자증권 실도입도 **망분리 대응이 일정·범위의 1순위 변수.** 로드맵에 별도 트랙 필요.

---

## 5. 물리적 제한 환경의 현장 애로 & 해결법

| 애로 | 현장 해결책 | 우리 적용 포인트 |
|------|------------|------------------|
| **GPU 비용/메모리** | 양자화 표준화: **FP8**(프로덕션 기본, H100/H200/MI300X 디코드 ~2배), 작은 건 **INT4/Q4(GGUF)**. 70B=H100/A100 2장, 11B급=1장 | Qwen3-30B-A3B MoE는 활성 3B라 1장으로도 가능 |
| **속도(클라우드比 5~10배 느림)** | **vLLM/SGLang**로 수렴(PagedAttention). 순정 HF pipeline은 GPU 놀림 | 기존 `OpenAIService`를 vLLM(OpenAI 호환)에 그대로 연결 |
| **모든 질의에 대형모델은 과함** | **모델 캐스케이딩**: Phi-3(200ms)→Mistral 7B(500ms)→Llama 70B(2s). **80%는 소형이 처리** | 우리 **confidence 재보정**과 직접 연결 — 쉬운 질의는 소형, 애매하면 대형 |
| **도메인 정확도** | 범용 70B보다 **LoRA/QLoRA 파인튜닝 7B가 특정 업무에 더 정확**. 증권 용어·법규 학습 | OLA-F·케이뱅크 사례. 향후 우리 편람으로 LoRA |
| **업데이트(인터넷 없음)** | 가중치를 **물리 매체(sneakernet)** 반입, 서명 번들로 분기 갱신. 다중 사이트는 가중치 델타만 | 모델·인덱스 반입 절차 SOP화 |
| **규제/감사** | PII 마스킹, 불변 감사로그→SIEM, **출처 추적성**, DRM/SSO 연동 | 우리 **출처표시**가 추적성 요건을 이미 일부 충족 |

---

## 6. 우리 프로젝트 실도입 권고

1. **아키텍처 유지** — bge-m3 + 하이브리드 + RAG + 출처는 글로벌·국내 표준과 일치. 재설계 불필요.
2. **생성 LLM 비교 테스트(3주차 계획 확장)** — 후보에 **(a) Qwen3-30B-A3B(글로벌 오픈웨이트)** + **(b) 국산 금융특화(업스테이지 Solar / 원라인 OLA-F / HyperCLOVA X)** 동시 포함, 30문항 한국어 증권 정확도로 비교.
3. **서빙: vLLM(OpenAI 호환)** — 기존 `OpenAIService`에 `base_url`만 바꿔 연결, chat/scorer/question_gen 코드 무변경.
4. **모델 캐스케이딩 + confidence 연계** — GPU 예산 절감(소형 우선, 애매할 때만 대형).
5. **망분리 대응 트랙 분리** — 모델 반입 SOP, egress 차단, DRM/SSO/PII, 감사로그.
6. **JSON 채점 회귀 테스트** — 모델 교체 시 훈련모드 채점 JSON 파싱 검증 필수.

---

## 출처

- [MindMap — Sovereign AI(표준 폐쇄망 스택)](https://www.mindmapdigital.ai/sovereign-ai)
- [TrueFoundry — Air-Gapped AI in Regulated Finance](https://www.truefoundry.com/blog/air-gapped-ai-deploying-enterprise-llms-in-highly-regulated-industries)
- [PredictionGuard — 규제산업 자체호스팅 모델](https://predictionguard.com/blog/best-self-hosted-ai-models-regulated-industries)
- [SOO Group — Air-Gapped(모델 캐스케이딩)](https://thesoogroup.com/blog/sandboxed-ai-deploying-llms-airgapped)
- [Yodo Labs — Qwen 온프레미스 금융 사례](https://yodolabs.jp/en/case-studies/on-premise-llm-financial-services)
- [한국투자증권(크라우드웍스)](https://www.dt.co.kr/article/12008996)
- [IBK투자증권(핑거·원라인 OLA-F)](https://www.datanet.co.kr/news/articleView.html?idxno=210440)
- [한국은행 BOKI](https://www.financialpost.co.kr/news/articleView.html?idxno=245044) · [BOKI(매경 영문)](https://www.mk.co.kr/en/it/11276322)
- [케이뱅크 프라이빗 LLM](https://v.daum.net/v/20250226085000105)
- [하나은행 H-GPT](http://www.choicenews.co.kr/news/articleView.html?idxno=148976)
- [우리투자증권(올거나이즈)](https://digitalchosun.dizzo.com/site/data/html_dir/2026/01/12/2026011280205.html)
- [삼성SDS — 2025 국내 은행 AI 전망](https://www.samsungsds.com/kr/insights/ai-in-banking-in-2025.html)
- [SitePoint — 2026 로컬 LLM 프로덕션 가이드](https://www.sitepoint.com/the-2026-definitive-guide-to-running-local-llms-in-production/)

*Last Updated: 2026-06-16*
