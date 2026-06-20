# -*- coding: utf-8 -*-
"""한화투자증권 PoC 공유회용 30분 발표자료(.pptx) 생성기.

- 산출물: docs/presentation/한화투자증권_AI상담_PoC_30min.pptx (16:9, ~34 슬라이드)
- 실행:  .venv/Scripts/python.exe docs/presentation/make_ppt_hanwha_poc.py
- 헬퍼는 make_ppt.py에서 '복사'(import 시 전역 prs 생성/save 부작용 회피) 후 한화 오렌지로 재색.
- 로고: 사용 안 함(요청). 표지/헤더는 텍스트 + 오렌지 액센트.
- 근거: 측정값(data/eval/*.json), 아키텍처(api-spec.md/architecture.md),
        리서치(RESEARCH_NOTES_2026-06-20.md 출처 인용).
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
import os

# ── 한화 디자인 토큰 ─────────────────────────────────────────
ORANGE = RGBColor(0xF3, 0x73, 0x21)   # 한화 오렌지 — 주 강조/결론
ORANGED = RGBColor(0xD8, 0x5C, 0x12)  # 진한 오렌지
NAVY = RGBColor(0x13, 0x29, 0x4B)     # 한화 네이비 — 제목/표지
TEAL = RGBColor(0x0F, 0x76, 0x6E)     # 보조(폐쇄망/실도입)
INK = RGBColor(0x1F, 0x29, 0x37)      # 본문
GRAY = RGBColor(0x6B, 0x72, 0x80)     # 부가
LIGHT = RGBColor(0xF3, 0xF4, 0xF6)    # 카드 배경
SOFT = RGBColor(0xFF, 0xF3, 0xEC)     # 오렌지 연한 배경
GOOD = RGBColor(0x15, 0x80, 0x3D)
BAD = RGBColor(0xB9, 0x1C, 0x1C)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT = "맑은 고딕"

SW, SH = Inches(13.333), Inches(7.5)

prs = Presentation()
prs.slide_width = SW
prs.slide_height = SH
BLANK = prs.slide_layouts[6]
_PAGE = [0]  # 페이지 카운터


# ── 헬퍼 (make_ppt.py 복사 + 확장) ───────────────────────────
def _ea(run):
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = rPr.makeelement(qn(tag), {})
            rPr.append(el)
        el.set("typeface", FONT)


def put_text(slide, x, y, w, h, lines, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for i, (text, size, bold, color, align) in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(4)
        run = p.add_run()
        run.text = text
        f = run.font
        f.name, f.size, f.bold = FONT, Pt(size), bold
        f.color.rgb = color
        _ea(run)
    return box


def rect(slide, x, y, w, h, fill, line=None, round_=True):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if round_ else MSO_SHAPE.RECTANGLE, x, y, w, h)
    if round_:
        try:
            shape.adjustments[0] = 0.06
        except Exception:
            pass
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if line:
        shape.line.color.rgb = line
        shape.line.width = Pt(1.5)
    else:
        shape.line.fill.background()
    shape.shadow.inherit = False
    return shape


def shape_text(shape, lines, anchor=MSO_ANCHOR.TOP):
    tf = shape.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.14)
    tf.margin_top = tf.margin_bottom = Inches(0.1)
    for i, (text, size, bold, color, align) in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(5)
        run = p.add_run()
        run.text = text
        f = run.font
        f.name, f.size, f.bold = FONT, Pt(size), bold
        f.color.rgb = color
        _ea(run)


def slide():
    _PAGE[0] += 1
    return prs.slides.add_slide(BLANK)


def header(s, kicker, title):
    rect(s, Inches(0.6), Inches(0.42), Inches(0.12), Inches(0.95), ORANGE, round_=False)
    put_text(s, Inches(0.9), Inches(0.35), Inches(11.8), Inches(0.4),
             [(kicker, 13, True, ORANGE, PP_ALIGN.LEFT)])
    put_text(s, Inches(0.9), Inches(0.68), Inches(11.8), Inches(0.75),
             [(title, 27, True, NAVY, PP_ALIGN.LEFT)])
    # 페이지 번호
    put_text(s, Inches(12.4), Inches(7.05), Inches(0.8), Inches(0.3),
             [(str(_PAGE[0]), 10, False, GRAY, PP_ALIGN.RIGHT)])


def takeaway(s, text, color=NAVY, y=Inches(6.5)):
    bar = rect(s, Inches(0.6), y, Inches(12.13), Inches(0.62), color)
    shape_text(bar, [(text, 14.5, True, WHITE, PP_ALIGN.CENTER)], anchor=MSO_ANCHOR.MIDDLE)


def footnote(s, text, y=Inches(6.95)):
    put_text(s, Inches(0.9), y, Inches(11.4), Inches(0.4),
             [(text, 9.5, False, GRAY, PP_ALIGN.LEFT)])


def option_cards(s, options, y=Inches(2.3), h=Inches(3.9)):
    n = len(options)
    gap = Inches(0.3)
    total = Inches(12.13)
    w = Emu(int((total - gap * (n - 1)) / n))
    x = Inches(0.6)
    for name, desc, pro, con, chosen in options:
        card = rect(s, x, y, w, h, WHITE if chosen else LIGHT, line=ORANGE if chosen else None)
        lines = [
            (("✅ " if chosen else "") + name, 15, True, ORANGE if chosen else INK, PP_ALIGN.LEFT),
            (desc, 11.5, False, GRAY, PP_ALIGN.LEFT),
            ("👍 " + pro, 12, False, GOOD, PP_ALIGN.LEFT),
            ("👎 " + con, 12, False, BAD, PP_ALIGN.LEFT),
        ]
        shape_text(card, lines)
        x = Emu(int(x + w + gap))


def flow(s, steps, y=Inches(3.0), h=Inches(1.1), color=NAVY):
    n = len(steps)
    gap = Inches(0.12)
    total = Inches(12.13)
    w = Emu(int((total - gap * (n - 1)) / n))
    x = Inches(0.6)
    for i, st in enumerate(steps):
        shp = s.shapes.add_shape(MSO_SHAPE.CHEVRON, x, y, w, h)
        shp.adjustments[0] = 0.35
        shp.fill.solid()
        shp.fill.fore_color.rgb = color if i < n - 1 else ORANGE
        shp.line.fill.background()
        shp.shadow.inherit = False
        shape_text(shp, [(st, 12.5, True, WHITE, PP_ALIGN.CENTER)], anchor=MSO_ANCHOR.MIDDLE)
        x = Emu(int(x + w + gap))


def kpi_cards(s, items, y=Inches(2.4), h=Inches(2.3)):
    """items: [(label, big, sub, color)]"""
    n = len(items)
    gap = Inches(0.3)
    total = Inches(12.13)
    w = Emu(int((total - gap * (n - 1)) / n))
    x = Inches(0.6)
    for label, big, sub, color in items:
        card = rect(s, x, y, w, h, LIGHT)
        shape_text(card, [
            (label, 12.5, True, GRAY, PP_ALIGN.CENTER),
            (big, 38, True, color, PP_ALIGN.CENTER),
            (sub, 11.5, False, INK, PP_ALIGN.CENTER),
        ], anchor=MSO_ANCHOR.MIDDLE)
        x = Emu(int(x + w + gap))


def bullets(s, x, y, w, h, lines, size=14, gap=6):
    """lines: [(text, color, bold)] 또는 (text,) — 불릿 텍스트박스."""
    box = s.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    for i, ln in enumerate(lines):
        text = ln[0]
        color = ln[1] if len(ln) > 1 else INK
        bold = ln[2] if len(ln) > 2 else False
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.space_after = Pt(gap)
        run = p.add_run()
        run.text = text
        f = run.font
        f.name, f.size, f.bold = FONT, Pt(size), bold
        f.color.rgb = color
        _ea(run)
    return box


def two_panel(s, left, right, y=Inches(2.0), h=Inches(3.9)):
    """left/right: (제목, 색, [라인...])"""
    for (title, col, lines), x in ((left, Inches(0.6)), (right, Inches(6.85))):
        card = rect(s, x, y, Inches(5.9), h, WHITE, line=col)
        body = [(title, 16, True, col, PP_ALIGN.LEFT)]
        for ln in lines:
            body.append((ln, 12.5, False, INK, PP_ALIGN.LEFT))
        shape_text(card, body)


def rows_table(s, rows, y=Inches(2.0), rh=Inches(0.86), highlight_idx=None):
    """rows: [(좌, 우)] 2열 카드 리스트. highlight_idx: 오렌지 강조 행 인덱스 set."""
    highlight_idx = highlight_idx or set()
    yy = y
    for i, (a, b) in enumerate(rows):
        hot = i in highlight_idx
        card = rect(s, Inches(0.6), yy, Inches(12.13), rh,
                    SOFT if hot else LIGHT, line=ORANGE if hot else None)
        tf = card.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_left = Inches(0.18)
        p = tf.paragraphs[0]
        r1 = p.add_run(); r1.text = a + "   "
        f = r1.font; f.name, f.size, f.bold = FONT, Pt(14), True
        f.color.rgb = ORANGED if hot else NAVY; _ea(r1)
        r2 = p.add_run(); r2.text = b
        f = r2.font; f.name, f.size, f.bold = FONT, Pt(12.5), False
        f.color.rgb = INK; _ea(r2)
        yy = Emu(int(yy + rh + Inches(0.12)))


# ════════════════════════════════════════════════════════════
# S1. 표지 (로고 없음)
# ════════════════════════════════════════════════════════════
s = slide()
rect(s, 0, 0, SW, SH, NAVY, round_=False)
rect(s, Inches(0.9), Inches(2.4), Inches(0.16), Inches(1.7), ORANGE, round_=False)
put_text(s, Inches(1.3), Inches(2.0), Inches(11), Inches(0.5),
         [("고객사 공유회 · Proof of Concept", 15, True, ORANGE, PP_ALIGN.LEFT)])
put_text(s, Inches(1.3), Inches(2.55), Inches(11.6), Inches(1.7),
         [("한화투자증권 AI 상담 어시스턴트", 42, True, WHITE, PP_ALIGN.LEFT),
          ("상담사가 실제로 쓰는 '응대 + 코칭 + 정합성' AI", 19, False, RGBColor(0xC7, 0xD2, 0xE4), PP_ALIGN.LEFT)])
put_text(s, Inches(1.3), Inches(5.7), Inches(11), Inches(0.9),
         [("업무편람 기반 RAG · 출처 인용 · 폐쇄망 이식형", 14, True, WHITE, PP_ALIGN.LEFT),
          ("FastAPI · React · ChromaDB · bge-m3(로컬 임베딩) · LLM 교체형", 12.5, False, RGBColor(0x9C, 0xA8, 0xBC), PP_ALIGN.LEFT)])

# ════════════════════════════════════════════════════════════
# S2. 아젠다
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "AGENDA", "오늘 이야기 — 30분")
items = [
    ("01", "무엇을 / 왜 만들었나", "문제정의 · 3개 기능(응대·AI코치·오답제보)"),
    ("02", "어떻게 작동하나", "아키텍처 · RAG 파이프라인 · 라이브 데모"),
    ("03", "정확도와 그 근거", "검색·답변 분리 측정 · 측정 방법론 · 차별화 기법"),
    ("04", "LLM 한계와 해결방향", "환각·최신성·도메인·망분리 — 업계 해결책 + 우리 적용"),
    ("05", "비전 & 실도입", "데이터 허브 · STT · 폐쇄망 로드맵 · ROI"),
]
y = Inches(1.85)
for num, t, d in items:
    card = rect(s, Inches(0.6), y, Inches(12.13), Inches(0.92), LIGHT)
    shape_text(card, [(f"{num}   {t}", 17, True, NAVY, PP_ALIGN.LEFT),
                      (d, 12, False, GRAY, PP_ALIGN.LEFT)], anchor=MSO_ANCHOR.MIDDLE)
    y = Emu(int(y + Inches(1.04)))

# ════════════════════════════════════════════════════════════
# S3. 문제정의
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "01 · 무엇을/왜", "문제 — 검색에 시간을 갈아넣고, 신입은 맨몸으로 배운다")
kpi_cards(s, [
    ("고객 1건 응대 중 편람 검색", "120~300초", "숙련자도 직접 검색", NAVY),
    ("신입이 혼자 응대까지", "약 3개월", "선배 1:1 OJT 필요", NAVY),
    ("지식이 흩어진 곳", "비정형", "메일·메신저·엑셀·편람", ORANGE),
], y=Inches(2.2), h=Inches(2.6))
put_text(s, Inches(0.9), Inches(5.2), Inches(11.6), Inches(1.0),
         [("• 정답은 편람·FAQ·선배 머릿속에 흩어져 있고, 찾는 일은 사람의 시간을 소모한다.", 14, False, INK, PP_ALIGN.LEFT),
          ("• 콜센터는 근무시간의 상당 부분을 '검색'에 쓴다(McKinsey·IDC: 정보탐색에 근무시간 20~30%).", 13, False, GRAY, PP_ALIGN.LEFT)])
takeaway(s, "검색도 교육도 사람의 시간을 쓰는 구조 → AI로 '응대 지원 + 코칭 + 정합성'을 함께 푼다")

# ════════════════════════════════════════════════════════════
# S4. 솔루션 — 3개 기능
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "01 · 무엇을/왜", "해결 — 하나의 답변DB, 세 가지 쓰임")
cards = [
    ("💬 응대 모드", ORANGE, ["고객 응대 중 편람 검색",
                          "질문 → 출처·신뢰도 + 답변(스트리밍)",
                          "추후 STT로 통화내용 자동 입력"]),
    ("🎓 AI 코치", NAVY, ["응대 상황 시뮬레이션 + 채점",
                        "고객 페르소나(말 긴/급한/불만/초보)",
                        "일반 CS 코칭 → 추후 콜센터 교육방식"]),
    ("⚑ 오답 제보", TEAL, ["답변 정합성을 상담사가 제보",
                        "사유 + 정답제안 → 로컬 저장",
                        "검토 → 답변/편람 보정(데이터 선순환)"]),
]
n = len(cards); gap = Inches(0.3); w = Emu(int((Inches(12.13) - gap * (n - 1)) / n)); x = Inches(0.6)
for title, col, lines in cards:
    card = rect(s, x, Inches(2.05), w, Inches(3.9), WHITE, line=col)
    body = [(title, 17, True, col, PP_ALIGN.LEFT)]
    for ln in lines:
        body.append(("• " + ln, 12.5, False, INK, PP_ALIGN.LEFT))
    shape_text(card, body)
    x = Emu(int(x + w + gap))
takeaway(s, "같은 업무편람 데이터를 — 응대는 '검색→답변', 코치는 '출제→채점', 제보는 '수집→개선'으로")

# ════════════════════════════════════════════════════════════
# S5. 데모 — 응대 모드
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "02 · 어떻게 작동", "라이브 데모 ① 응대 모드")
two_panel(s,
          ("화면 흐름", NAVY, ["1. 상담사가 자연어로 질문",
                            "2. 검색 즉시 '출처 + 신뢰도 뱃지' 선표시",
                            "3. 답변이 토큰 단위로 스트리밍",
                            "4. 답변 아래 '⚑ 오답 제보' 링크",
                            "5. 입력창 옆 🎙️ (STT 자리, 준비중)"]),
          ("이 데모에서 보실 것", ORANGE, ["• 출처가 답변보다 먼저 뜬다(SSE)",
                                    "• [1][2] 인용번호 ↔ 출처 1:1",
                                    "• 신뢰도 high/medium/low 뱃지",
                                    "• 편람에 없으면 '확인되지 않음' 거부",
                                    "• 한화 오렌지 UI(상담사 대면용)"]))
footnote(s, "* 데모 PC는 폐쇄망 대비 로컬 임베딩(bge-m3). 답변 생성 LLM만 교체 지점.")

# ════════════════════════════════════════════════════════════
# S6. 데모 — AI 코치
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "02 · 어떻게 작동", "라이브 데모 ② AI 코치 — '어떤 고객이 올지 모른다'")
two_panel(s,
          ("시뮬레이션 루프", NAVY, ["1. 난이도 + 고객 상황(페르소나) 선택",
                              "2. AI가 고객役으로 질문 출제",
                              "3. 신입이 응대 답변 작성",
                              "4. AI가 채점 + CS 코칭 피드백",
                              "5. 모범답변 · 편람 출처 제공"]),
          ("고객 페르소나(상황)", ORANGE, ["• 일반(표준) 고객",
                                    "• 말이 긴/장황한 고객",
                                    "• 급한/조급한 고객",
                                    "• 불만/화난 고객 → 공감·진정",
                                    "• 초보 고객 → 쉬운 설명"]))
takeaway(s, "실환경엔 다양한 고객이 인입된다 → 상황별 응대를 '안전하게 미리' 훈련")

# ════════════════════════════════════════════════════════════
# S7. 데모 — 오답 제보 → 검토(데이터 선순환)
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "02 · 어떻게 작동", "라이브 데모 ③ 오답 제보 → 검토 (데이터 선순환)")
flow(s, ["답변 의심", "⚑ 제보(사유+정답제안)", "로컬 SQLite 축적", "운영자 검토", "편람/답변 보정"],
     y=Inches(2.2), h=Inches(1.15))
put_text(s, Inches(0.9), Inches(3.9), Inches(11.6), Inches(2.0),
         [("• 제보 시 질문·답변·출처·신뢰도를 '스냅샷'으로 함께 저장 → 재현·추적 가능", 14, False, INK, PP_ALIGN.LEFT),
          ("• 검토 화면: 미처리/처리완료 필터, '처리완료'는 선점형 상태변경(이중 처리 방지)", 14, False, INK, PP_ALIGN.LEFT),
          ("• 폐쇄망 대비 외부 의존 0 — 파일 DB 1개(data/feedback.db)", 14, False, INK, PP_ALIGN.LEFT),
          ("• 이 루프가 곧 '답변DB 품질을 키우는 데이터 플라이휠'의 출발점", 14, True, ORANGED, PP_ALIGN.LEFT)])
takeaway(s, "틀린 답을 '버그가 아니라 데이터'로 바꾼다 — 쓸수록 좋아지는 구조", color=TEAL)

# ════════════════════════════════════════════════════════════
# S8. 아키텍처 전경
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "02 · 어떻게 작동", "시스템 아키텍처 — 폐쇄망 이식을 전제로 설계")
flow(s, ["상담사(React)", "FastAPI", "검색(ChromaDB)", "LLM 답변생성", "출처+답변"],
     y=Inches(2.1), h=Inches(1.1))
rows = [
    ("프론트  React + Vite", "응대/AI코치/제보검토 3화면, SSE 스트리밍 소비, 한화 오렌지 UI"),
    ("백엔드  FastAPI", "라우터(얇음) + 서비스(RAG·채점·제보) 분리, LLM 추상화(4메서드)"),
    ("검색  ChromaDB(2컬렉션)", "faq_titles + faq_contents, 코사인, 파일기반(폴더복사=이식)"),
    ("임베딩  bge-m3(로컬)", "1024차원, 오프라인·무료, 폐쇄망 그대로. 생성 LLM만 교체 지점"),
]
rows_table(s, rows, y=Inches(3.5), rh=Inches(0.7), highlight_idx={3})
footnote(s, "출처: docs/architecture.md, docs/api-spec.md (단일 진실 소스)")

# ════════════════════════════════════════════════════════════
# S9. 왜 RAG (파인튜닝 아님)
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "03 · 정확도/근거", "왜 파인튜닝이 아니라 RAG인가")
flow(s, ["질문", "임베딩", "ChromaDB 검색", "LLM이 문서 참고", "답변+출처"], y=Inches(2.2), h=Inches(1.1))
c = rect(s, Inches(0.6), Inches(3.7), Inches(12.13), Inches(2.4), LIGHT)
shape_text(c, [("모델은 그대로, 문서를 검색해 근거로 보여준다", 16, True, NAVY, PP_ALIGN.LEFT),
               ("• 편람이 바뀌면? → 재학습 없이 재인제스트만 (최신성)", 14, False, INK, PP_ALIGN.LEFT),
               ("• '어디서 나온 답?' → 검색한 문서가 곧 출처 (금융 도메인 필수)", 14, False, INK, PP_ALIGN.LEFT),
               ("• 문서에 없으면 '확인되지 않음' 강제 → 환각 억제", 14, False, INK, PP_ALIGN.LEFT)])
takeaway(s, "자주 바뀌는 사내문서 + 출처 의무 → 구조적으로 RAG가 유리")

# ════════════════════════════════════════════════════════════
# S10. 왜 ChromaDB
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "03 · 정확도/근거", "왜 벡터DB로 ChromaDB — 기준은 '폐쇄망 이식성'")
option_cards(s, [
    ("Pinecone", "클라우드 전용 SaaS", "관리 불필요", "폐쇄망 반입 불가 → 탈락", False),
    ("Milvus", "분산 벡터DB", "초대규모 대응", "서버·etcd 설치 복잡, PoC 과함", False),
    ("FAISS", "검색 라이브러리", "가볍고 빠름", "DB 아님 — 메타데이터 직접 구현", False),
    ("ChromaDB", "파일기반 임베디드", "설치 한 줄 + 폴더 복사=이식", "초대규모엔 부적합(PoC 충분)", True),
], y=Inches(2.1), h=Inches(4.0))
takeaway(s, "폐쇄망 배포는 '파일 복사'가 가장 강력 — 서버 없는 ChromaDB")

# ════════════════════════════════════════════════════════════
# S11. 차별화 ① 제목+본문 분리
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "03 · 정확도/근거", "검색 품질 ① 제목·본문 분리 임베딩 (vs 일반 RAG)")
put_text(s, Inches(0.9), Inches(1.55), Inches(11.6), Inches(0.5),
         [("문제: 본문이 길수록 제목의 주제 신호가 희석 → '양도세' 같은 짧은 질문에 취약", 14, False, GRAY, PP_ALIGN.LEFT)])
option_cards(s, [
    ("본문만 임베딩", "단일 컬렉션", "단순", "긴 본문서 주제 매칭 약화", False),
    ("제목+본문 합쳐", "단일 컬렉션", "단순", "가중치 조절 불가", False),
    ("두 컬렉션 분리+가중병합", "faq_titles / faq_contents", "제목:본문 비율 튜닝 가능", "임베딩 2배·ID 정합 관리", True),
], y=Inches(2.2), h=Inches(3.7))
footnote(s, "일반 RAG는 보통 단일 컬렉션. 우리는 제목·본문 2컬렉션 가중병합(사람인 HR챗봇 87% 사례 참고).")

# ════════════════════════════════════════════════════════════
# S12. 차별화 ② Max Pooling + 동의어
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "03 · 정확도/근거", "검색 품질 ② Max Pooling + 동의어 확장")
two_panel(s,
          ("다중 제목 → Max Pooling", NAVY, ["문서 1개에 동의어 제목 여러 개",
                                       "합산=제목 많은 문서 편향 ❌",
                                       "평균=강한 일치 희석 ❌",
                                       "✅ 최댓값: 가장 잘 맞은 제목 1개",
                                       "순서: Max Pooling → 가중병합"]),
          ("동의어 확장(오프라인 사전)", ORANGE, ["'미국 주식'→'해외주식' 등 추가",
                                       "임베딩·BM25 쿼리만 확장",
                                       "LLM에 가는 원문 질문은 불변",
                                       "결정적·오프라인(폐쇄망·재현)",
                                       "데모 retrieval 미스 직접 수정"]))
takeaway(s, "동의어를 마음껏 추가해도 공정 — '튜닝 가능한 검색 구조'를 산다")

# ════════════════════════════════════════════════════════════
# S13. 차별화 ③ Hybrid Search
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "03 · 정확도/근거", "검색 품질 ③ Hybrid Search (BM25 + 벡터 RRF)")
kpi_cards(s, [
    ("hit@1 (16문항)", "62 → 81%", "+19%p", ORANGE),
    ("MRR", "0.79 → 0.88", "+0.09", ORANGE),
    ("정렬 vs 점수", "분리", "RRF로 정렬, 점수는 벡터 유지", NAVY),
], y=Inches(2.1), h=Inches(2.2))
put_text(s, Inches(0.9), Inches(4.6), Inches(11.6), Inches(1.5),
         [("• 벡터(의미) + BM25(키워드)를 RRF로 융합 → 고유명사·코드(K-OTC, [11124], OTP)에 강함", 14, False, INK, PP_ALIGN.LEFT),
          ("• confidence 임계값이 벡터 점수 기준이라, 정렬만 RRF로 바꾸고 score는 벡터 유사도 유지", 13, False, GRAY, PP_ALIGN.LEFT),
          ("• 한국어 문자 bigram 토크나이저(조사 무관 매칭). kiwipiepy는 한글경로 세그폴트로 제외", 13, False, GRAY, PP_ALIGN.LEFT)])
takeaway(s, "의미검색만으로 약한 '정확한 단어' 질의를 키워드축이 보완")

# ════════════════════════════════════════════════════════════
# S14. 차별화 ④ confidence 재보정 + 출처중복제거 + SSE
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "03 · 정확도/근거", "검색 품질 ④ 측정 기반 보정 · 출처 정합 · 선전송")
rows_table(s, [
    ("confidence 재보정", "bge-m3 점수분포(정답1위 0.30~0.78) 실측 → 임계값 0.85/0.70 → 0.70/0.50"),
    ("출처 페이지 중복제거", "같은 페이지 청크가 top_k 독식 방지(페이지당 캡) → 출처 [n] 1:1 정합"),
    ("출처 선전송(SSE)", "검색 끝나면 출처·신뢰도 먼저 전송 → LLM 기다리지 않고 첫 응답 1초"),
    ("LLM 추상화", "generate/stream/embed/count 4메서드 → 모델 교체 = 구현체 1개 + DI 1곳"),
], y=Inches(2.0), rh=Inches(0.92), highlight_idx={0})
takeaway(s, "정확도는 모델이 아니라 '측정→보정' 루프에서 나온다", color=TEAL)

# ════════════════════════════════════════════════════════════
# S15. 측정 방법론
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "03 · 정확도/근거", "어떻게 측정했나 — 검색과 답변을 '분리' 측정")
two_panel(s,
          ("① 검색 정확도 (retrieval)", NAVY, ["정답 키워드/출처가 top-k 안에?",
                                        "지표: hit@1 / hit@3 / hit@5 / MRR",
                                        "30문항 평가셋(거래·계좌·수수료 등)",
                                        "→ 리포트 파일로 '재현 가능'"]),
          ("② 답변 정확도 (generation)", ORANGE, ["생성 답변이 정답 사실을 담았나?",
                                          "키워드 채점(공백무시) = 하한값",
                                          "LLM 의미채점(--judge): 패러프레이즈 보정",
                                          "→ '표현 달라도 의미 맞으면 정답'"]))
footnote(s, "도구: scripts/test_accuracy.py  ·  '검색 hit인데 답변 miss = 프롬프트 문제 / 검색 miss = 검색 문제'로 원인 분리")

# ════════════════════════════════════════════════════════════
# S16. 검색 정확도 (하드 증빙)
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "03 · 정확도/근거", "검색 정확도 — hit@3 100% (저장 리포트로 증빙)")
kpi_cards(s, [
    ("hit@1", "70%", "정답이 1순위", NAVY),
    ("hit@3", "100%", "정답이 top-3 안", ORANGE),
    ("hit@5", "100%", "정답이 top-5 안", NAVY),
    ("MRR", "0.84", "평균 역순위", NAVY),
], y=Inches(2.2), h=Inches(2.3))
put_text(s, Inches(0.9), Inches(4.8), Inches(11.6), Inches(1.2),
         [("• 30문항 평가셋, bge-m3 로컬 임베딩 기준. 정답 문서가 항상 검색 상위 3개 안에 든다.", 14, False, INK, PP_ALIGN.LEFT),
          ("• 정답 1위 top_score 분포 0.30~0.78(최댓값 0.78) → confidence 재보정의 근거.", 13, False, GRAY, PP_ALIGN.LEFT)])
footnote(s, "근거 파일: data/eval/accuracy_bge_m3_search_20260613_095753.json (재현 가능)")

# ════════════════════════════════════════════════════════════
# S17. 답변 정확도 (방법론 + 재현)
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "03 · 정확도/근거", "답변 정확도 — LLM 의미채점 80% (방법론 + 재현)")
two_panel(s,
          ("측정값", ORANGE, ["LLM 의미채점: 12/15 = 80%",
                          "키워드 채점(하한): 15/24 ≈ 63%",
                          "→ 키워드는 패러프레이즈를 못 잡음",
                          "→ 의미채점이 실제값에 더 근접"]),
          ("정직한 한계 표기", NAVY, ["답변 정확도 100%는 불가(LLM 특성)",
                              "저신뢰 시 '확인되지 않음' 폴백",
                              "재현: test_accuracy.py --answers --judge",
                              "* 30문항 전수 재측정은 일일 무료한도로 보류"]))
takeaway(s, "검색은 '하드 증빙', 답변은 '방법론 + 재현 절차'로 정직하게 제시")

# ════════════════════════════════════════════════════════════
# S18. 차별화 요약표
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "03 · 정확도/근거", "일반적 RAG와 다르게 한 것 — 요약")
rows_table(s, [
    ("① 제목·본문 2컬렉션", "주제 신호 보존 + 제목:본문 비율 튜닝(일반 RAG는 단일 컬렉션)"),
    ("② Max Pooling", "동의어 제목 다수에도 공정 — 합산/평균의 편향·희석 회피"),
    ("③ Hybrid(BM25+벡터)", "고유명사·코드 강함 — hit@1 62→81%"),
    ("④ 동의어 사전(오프라인)", "결정적·폐쇄망 친화 — 임베딩/BM25만 확장"),
    ("⑤ confidence 측정 재보정", "임베딩 점수분포 실측으로 임계값 보정 + 출처중복제거"),
], y=Inches(1.95), rh=Inches(0.82), highlight_idx={0, 1, 2, 3, 4})
footnote(s, "근거: docs/ANSWER_QUALITY.md(적용/폐기 로그), docs/api-spec.md 섹션 3·10")

# ════════════════════════════════════════════════════════════
# S19. LLM 한계 ① 환각
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "04 · LLM 한계/해결", "한계 ① 환각 — '그럴듯하게 틀린 답'")
two_panel(s,
          ("업계의 4단계 방어선", NAVY, ["① 그라운딩(Vertex/Azure On Your Data)",
                                 "② 출처 표기(Galileo Chunk Attribution)",
                                 "③ 사후검증(NeMo Guardrails·Bedrock)",
                                 "④ 거부/기권(Cleanlab TLM)",
                                 "'오답은 기권보다 나쁘다'"]),
          ("우리 적용 / 향후", ORANGE, ["bge-m3 + confidence + 출처중복제거",
                               "저신뢰 시 '확인되지 않음' 폴백",
                               "향후: RAGAS Faithfulness 자동채점",
                               "향후: BGE Reranker v2(+15%p)",
                               "고위험 답변은 상담원 검토 유지"]))
footnote(s, "근거: OpenAI 'why LMs hallucinate', 스탠퍼드 법률RAG(잔존 17~33%) — RAG는 70~90%↓이나 0%는 아님")

# ════════════════════════════════════════════════════════════
# S20. LLM 한계 ② 최신성 / ③ 도메인
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "04 · LLM 한계/해결", "한계 ② 최신성 · ③ 도메인 정확도")
two_panel(s,
          ("② 최신성(컷오프)", NAVY, ["재학습 ❌ → RAG + 증분 재인덱싱",
                               "문서 변경 이벤트로 자동 갱신",
                               "2025 트렌드: Agentic RAG",
                               "시세·공시는 도구 호출로 우회",
                               "우리: 내부문서 RAG로 최신성 확보"]),
          ("③ 도메인 정확도", ORANGE, ["RAG=오픈북 / 파인튜닝=클로즈드북 / 가드레일=감독관",
                                "멀티에이전트 RAG 56% vs GPT-4 19%(FinanceBench)",
                                "→ '검색 설계 > 모델 선택'",
                                "BloombergGPT(50B)도 GPT-4에 밀림",
                                "우리: RAG 우선, 향후 LoRA로 톤·포맷"]))
footnote(s, "근거: arxiv 2501.09136(Agentic RAG), Red Hat(RAG vs FT), intuitionlabs(FinanceBench)")

# ════════════════════════════════════════════════════════════
# S21. LLM 한계 ④ 보안/망분리
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "04 · LLM 한계/해결", "한계 ④ 보안·규제·망분리 — 한국 특유의 최대 변수")
rows_table(s, [
    ("규제 환경", "금융위 '망분리 개선 로드맵'(2024-08) — 74개사 141건 혁신금융 특례 신청"),
    ("국산 모델 선택지", "HyperCLOVA X(미래에셋 온프레미스) · EXAONE · Qwen3-30B(카카오뱅크) · Solar(신한DS)"),
    ("모델 선정 방법", "LG CNS 금융 AI 평가도구 — 29지표·1200문항으로 오픈모델 비교"),
    ("거버넌스", "휴먼인더루프 → governance-in-the-loop, 감사로그·추적성, 모델 캐스케이딩"),
], y=Inches(2.0), rh=Inches(0.92), highlight_idx={1})
takeaway(s, "우리는 폐쇄망 이식형으로 설계 — '바꿀 곳은 답변 LLM 단 1곳'", color=TEAL)

# ════════════════════════════════════════════════════════════
# S22. 데이터 허브 비전
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "05 · 비전/실도입", "비전 ① 데이터 허브 — 비정형 데이터를 답변DB로")
put_text(s, Inches(0.9), Inches(1.55), Inches(11.6), Inches(0.5),
         [("현재: 업무편람(정형) 단일 소스  →  향후: 메일·메신저·엑셀·회의록까지 통합", 14, True, NAVY, PP_ALIGN.LEFT)])
rows_table(s, [
    ("일본 SMBC", "사내 규정·매뉴얼 약 130만 건 RAG 횡단검색 + 참조자료 병기"),
    ("일본 미즈호 / 일본생명", "사무수속 RAG 해결률 96% · 약관 Claude RAG 유효답변 90%(엑셀 병합셀 판독)"),
    ("국내 신한투자/미래에셋/키움", "사내문서 RAG · 온프레미스 sLLM(HCX-DASH) · 업무상담 챗봇"),
    ("기술 파이프라인", "파싱(OCR)→정규화→메타데이터(Contextual)→중복제거→PII마스킹→ACL 보존"),
], y=Inches(2.15), rh=Inches(0.86), highlight_idx={3})
footnote(s, "출처: RESEARCH_NOTES_2026-06-20.md (SMBC dx-consultant, 미즈호/일본생명 IR, 각 사 보도)")

# ════════════════════════════════════════════════════════════
# S23. STT 비전
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "05 · 비전/실도입", "비전 ② STT 연동 — 타이핑 없는 응대 지원")
flow(s, ["고객 통화", "실시간 STT", "자동 질의 입력", "답변·출처 표시", "상담사는 응대에 집중"],
     y=Inches(2.3), h=Inches(1.15))
put_text(s, Inches(0.9), Inches(4.0), Inches(11.6), Inches(1.6),
         [("• 현재 UI에 STT 자리(🎙️)를 미리 배치 — 상담사가 타이핑하지 않아도 통화 내용이 질의로 입력", 14, False, INK, PP_ALIGN.LEFT),
          ("• 국내 콜센터 STT+AI 검색 결합 사례 다수 — 인프라(온프레미스 vs 클라우드)·성능 지표 참고", 13, False, GRAY, PP_ALIGN.LEFT),
          ("• 응대 중 손이 자유로워지고, 통화-답변 정합 로그가 그대로 학습 데이터가 됨", 14, True, ORANGED, PP_ALIGN.LEFT)])
takeaway(s, "STT는 '입력 자동화'이자 '데이터 수집'의 두 마리 토끼")

# ════════════════════════════════════════════════════════════
# S24. 폐쇄망 실도입 로드맵
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "05 · 비전/실도입", "폐쇄망 실도입 — 바꿀 곳은 단 1곳")
rows_table(s, [
    ("LLM(답변생성)", "Gemini API  →  사내 LLM(Qwen3-30B / HyperCLOVA X / Solar 후보)  ★교체"),
    ("임베딩", "bge-m3(1024) 로컬 — 그대로(오프라인·무료)"),
    ("벡터DB", "ChromaDB 파일기반 — 폴더 복사로 이식 끝"),
    ("백엔드/UI", "FastAPI + React — 추상화 뒤라 변경 없음"),
], y=Inches(2.0), rh=Inches(0.92), highlight_idx={0})
put_text(s, Inches(0.9), Inches(5.9), Inches(11.6), Inches(0.5),
         [("수집 자동 최신화: 변경감지→지문대조→청킹→로컬임베딩→ChromaDB (증분 임베딩 95%+ 절감)", 12.5, False, GRAY, PP_ALIGN.LEFT)])
takeaway(s, "처음부터 폐쇄망을 보고 고른 선택 — PoC 시행착오가 그대로 실도입 매뉴얼", color=TEAL)

# ════════════════════════════════════════════════════════════
# S25. 실환경 난관 해결(신뢰도)
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "05 · 비전/실도입", "실환경 난관 — 이미 부딪히고 해결했다")
rows_table(s, [
    ("사내망 SSL 인터셉트", "Zscaler 자체 CA → SSL_CERT_FILE/CA 번들 동기화(verify=False 안 씀)"),
    ("외부 의존 리스크", "API 크레딧 소진 경험 → LLM 추상화로 모델 교체 비용 최소화"),
    ("PDF 표·개조식 파싱", "Docling(표 구조 보존) + 한국어 개조식 번호 정규식 보강"),
    ("위키 증분 수집", "content-hash diff로 변경분만 임베딩(95%+ 호출 절감)"),
], y=Inches(2.0), rh=Inches(0.92))
footnote(s, "근거: docs/TROUBLESHOOTING.md, docs/adr/ (결정·대안·교훈 기록)")

# ════════════════════════════════════════════════════════════
# S26. ROI
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "05 · 비전/실도입", "기대 효과 — 검색 시간 절감 ROI")
kpi_cards(s, [
    ("편람 검색", "300초 → 3초", "응답 체감", ORANGE),
    ("분기 절감(추정)", "2.7~3.8 M/M", "검색시간 35%↓ 가정", NAVY),
    ("분기 처리콜(예시)", "78,546콜", "39명·38콜/일·53일", NAVY),
], y=Inches(2.2), h=Inches(2.3))
put_text(s, Inches(0.9), Inches(4.8), Inches(11.6), Inches(1.2),
         [("산정: 39명 × 검색 1.8~2.5h/일 × 53영업일 × 35%↓ = 분기 1,300~1,810h ≈ 2.7~3.8 M/M", 13.5, False, INK, PP_ALIGN.LEFT),
          ("* 인력·콜 수는 예시 파라미터. 실도입 시 한화 실측치로 재산정.", 12, False, GRAY, PP_ALIGN.LEFT)])
takeaway(s, "정성효과: 신입 온보딩 단축 · 응대 품질 균일화 · 지식 자산화")

# ════════════════════════════════════════════════════════════
# S27. 도입 일정
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "05 · 비전/실도입", "제안 — 단계별 도입 로드맵")
flow(s, ["① PoC 검증", "② 응대 모드 확대", "③ AI코치/제보 운영", "④ 데이터허브·STT", "⑤ 폐쇄망 본도입"],
     y=Inches(2.3), h=Inches(1.15))
put_text(s, Inches(0.9), Inches(4.0), Inches(11.6), Inches(1.6),
         [("• 1단계: 현재 PoC를 한화 업무편람 일부로 검증(정확도·체감속도)", 14, False, INK, PP_ALIGN.LEFT),
          ("• 2~3단계: 응대 모드 실사용 + 오답 제보로 답변DB 품질 향상", 14, False, INK, PP_ALIGN.LEFT),
          ("• 4~5단계: 비정형 데이터 허브 + STT 연동, 사내 LLM으로 폐쇄망 본도입", 14, False, INK, PP_ALIGN.LEFT)])
takeaway(s, "작게 검증하고, 데이터 선순환으로 키우고, 폐쇄망으로 안착")

# ════════════════════════════════════════════════════════════
# S28. 리스크 & 완화
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "05 · 비전/실도입", "리스크 & 완화")
rows_table(s, [
    ("환각/오답", "출처표기 + confidence 게이트 + 오답제보 + 고위험 상담원 검토"),
    ("데이터 보안", "폐쇄망 온프레미스 + PII 마스킹 + ACL 보존(임베딩 단계)"),
    ("최신성", "변경 트리거 증분 재인덱싱 운영 규율"),
    ("정확도 전이", "벤더 수치는 참고 — 한화 코퍼스로 PoC 실측 검증"),
], y=Inches(2.0), rh=Inches(0.92))
footnote(s, "모든 외부 인용 수치는 자체 발표값 — 한화 환경 실측으로 검증 권장")

# ════════════════════════════════════════════════════════════
# S29. 요청사항
# ════════════════════════════════════════════════════════════
s = slide()
header(s, "마무리", "한화 측에 요청드리는 것")
rows_table(s, [
    ("데이터 접근", "업무편람·FAQ 일부 샘플(정확도 실측용) + (가능 시) 상담 로그 비식별 샘플"),
    ("STT 연동", "콜 인프라/녹취 연동 가능 범위 협의"),
    ("모델·인프라", "폐쇄망 GPU/사내 LLM 후보(HyperCLOVA X/Qwen/Solar) 및 망분리 정책 확인"),
    ("브랜딩", "공식 로고/가이드(필요 시) — 현재는 텍스트 + 한화 오렌지로 구성"),
], y=Inches(2.0), rh=Inches(0.92))
takeaway(s, "작은 데이터로 빠르게 실측 → 효과를 숫자로 확인하고 다음 단계 결정")

# ════════════════════════════════════════════════════════════
# S30. 클로징
# ════════════════════════════════════════════════════════════
s = slide()
rect(s, 0, 0, SW, SH, NAVY, round_=False)
put_text(s, Inches(1.25), Inches(1.7), Inches(11), Inches(3.6),
         [("세 줄 요약", 18, True, ORANGE, PP_ALIGN.LEFT),
          ("1.  응대 + AI코치 + 오답제보 — 하나의 답변DB로 상담을 지원·훈련·개선한다", 17, True, WHITE, PP_ALIGN.LEFT),
          ("2.  정확도는 구조에서 나온다 — 2컬렉션·Max Pooling·Hybrid·측정 재보정 (검색 hit@3 100%)", 17, True, WHITE, PP_ALIGN.LEFT),
          ("3.  처음부터 폐쇄망 이식형 — 바꿀 곳은 답변 LLM 단 1곳", 17, True, WHITE, PP_ALIGN.LEFT)])
put_text(s, Inches(1.25), Inches(5.9), Inches(11), Inches(0.8),
         [("Q&A   |   근거: docs/api-spec.md · ANSWER_QUALITY.md · ONPREM_ROADMAP.md · RESEARCH_NOTES_2026-06-20.md", 13, False, RGBColor(0xC7, 0xD2, 0xE4), PP_ALIGN.LEFT)])

# ── 저장 ────────────────────────────────────────────────────
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "한화투자증권_AI상담_PoC_30min.pptx")
prs.save(out)
print(f"저장 완료: {out}  (슬라이드 {len(prs.slides._sldIdLst)}장)")
