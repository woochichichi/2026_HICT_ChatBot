# -*- coding: utf-8 -*-
"""
증권 발표용 신규 PPT 빌드 (녹취록 260723 + 2차 피드백 반영, 15분 분량)
2차 피드백:
 - 상단 진행 네비게이션 바 추가(배경→만든것→어려웠던점→시연→도입·비전)
 - '벽' → '어려웠던 점'으로 프레임/명칭 변경
 - 줄글 → 개조식으로 설명 간결화
 - 구조 재정렬: 시연을 어려웠던 점 뒤로, 도입 고려+비전을 끝으로
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

# ---- 디자인 토큰 (원본 덱에서 추출) ----
ORANGE = RGBColor(0xFF, 0x66, 0x00)
DARK   = RGBColor(0x2A, 0x2A, 0x2A)
GRAY   = RGBColor(0x56, 0x56, 0x56)
LGRAY  = RGBColor(0x8C, 0x8C, 0x89)
BORDER = RGBColor(0xD6, 0xD6, 0xD2)
CREAM  = RGBColor(0xFF, 0xF6, 0xEF)
GREEN  = RGBColor(0x1E, 0x7A, 0x3C)
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
BAND   = RGBColor(0x2A, 0x2A, 0x2A)
FAINT  = RGBColor(0xD9, 0xD9, 0xD6)
NAVOFF = RGBColor(0xA8, 0xA8, 0xA4)
FONT   = "맑은 고딕"

SECTIONS = ["배경", "만든 것", "어려웠던 점", "시연", "도입·비전"]

prs = Presentation()
prs.slide_width  = Emu(12192000)
prs.slide_height = Emu(6858000)
BLANK = prs.slide_layouts[6]

def slide():
    return prs.slides.add_slide(BLANK)

def _set_font(run, size, color, bold, font=FONT):
    run.font.name = font
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.font.bold = bold
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find(qn('a:ea'))
    if ea is None:
        ea = rPr.makeelement(qn('a:ea'), {}); rPr.append(ea)
    ea.set('typeface', font)

def txt(s, l, t, w, h, text, size=12, color=DARK, bold=False,
        align=PP_ALIGN.LEFT, font=FONT, anchor=MSO_ANCHOR.TOP, wrap=True, line=None):
    tb = s.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = wrap; tf.vertical_anchor = anchor
    for m in ('margin_left','margin_right','margin_top','margin_bottom'):
        setattr(tf, m, 0)
    lines = text if isinstance(text, list) else [text]
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if line is not None: p.line_spacing = line
        runs = ln if isinstance(ln, list) else [(ln, {})]
        for seg, ov in runs:
            r = p.add_run(); r.text = seg
            _set_font(r, ov.get('size', size), ov.get('color', color),
                      ov.get('bold', bold), ov.get('font', font))
    return tb

def rrect(s, l, t, w, h, fill, linecol=None, radius=0.12):
    shp = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(l), Inches(t), Inches(w), Inches(h))
    shp.fill.solid(); shp.fill.fore_color.rgb = fill
    if linecol is None: shp.line.fill.background()
    else: shp.line.color.rgb = linecol; shp.line.width = Pt(1)
    shp.shadow.inherit = False
    try: shp.adjustments[0] = radius
    except Exception: pass
    return shp

def card(s, l, t, w, h, fill=WHITE, linecol=BORDER):
    return rrect(s, l, t, w, h, fill, linecol, radius=0.06)

def band(s, text, l=0.84, t=6.05, w=11.65, h=0.62, size=11.5):
    b = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(l), Inches(t), Inches(w), Inches(h))
    b.fill.solid(); b.fill.fore_color.rgb = BAND; b.line.fill.background(); b.shadow.inherit = False
    tf = b.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.25); tf.margin_right = Inches(0.25); tf.margin_top = 0; tf.margin_bottom = 0
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.LEFT
    r = p.add_run(); r.text = text; _set_font(r, size, WHITE, True)
    return b

def nav(s, active):
    """상단 진행 바. active=현재 섹션 idx(0-4) 또는 None."""
    x0, total, y, ph = 0.84, 11.65, 0.30, 0.38
    slot = total / len(SECTIONS)
    for i, name in enumerate(SECTIONS):
        cx = x0 + i*slot
        label = f"{i+1}  {name}"
        if i == active:
            rrect(s, cx+0.06, y, slot-0.12, ph, ORANGE, radius=0.5)
            txt(s, cx+0.06, y, slot-0.12, ph, label, 11, WHITE, True,
                align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, wrap=False)
        else:
            col = GRAY if (active is not None and i < active) else NAVOFF
            txt(s, cx+0.06, y, slot-0.12, ph, label, 10.5, col, False,
                align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, wrap=False)

def header(s, active, title, subtitle):
    nav(s, active)
    txt(s, 1.1, 0.92, 11.3, 0.55, title, 23, DARK, True)
    if subtitle:
        txt(s, 1.1, 1.52, 11.4, 0.4, subtitle, 12, GRAY)

def footer(s, page):
    txt(s, 0.84, 7.14, 3.2, 0.16, "ⓒ Hanwha Systems. All rights reserved", 7.5, LGRAY)
    txt(s, 6.24, 7.14, 0.85, 0.16, f"- {page} -", 7.5, LGRAY, align=PP_ALIGN.CENTER)

KICK = "한화시스템 ITO · 2026 AX Day"

# =====================================================================
# 1. 표지 (nav 없음)
# =====================================================================
s = slide()
txt(s, 1.1, 1.5, 11.0, 0.3, KICK, 13, ORANGE, True)
txt(s, 1.1, 2.05, 11.3, 1.4, [[("ITO ", {'color':DARK}), ("AX Day", {'color':ORANGE})]], 38, DARK, True)
txt(s, 1.1, 3.15, 11.2, 0.7, "직접 만든 RAG 상담 어시스턴트 — 만든 것 · 어려웠던 점 · 앞으로의 계획", 15, GRAY)
kw = [
    ("직접 만들었다", "편람을 출처와 함께 답하는 AI를 팀이 직접 구현·검증", WHITE),
    ("난점을 해결했다", "개발도구·인증·매일 바뀌는 편람 — 현장 난점을 직접 해결", CREAM),
    ("다음을 계획한다", "사내 환경이 갖춰지면 바로 적용되도록 설계", WHITE),
]
cw, gap, x0, y = 3.55, 0.4, 1.1, 4.35
for i, (h, d, f) in enumerate(kw):
    x = x0 + i*(cw+gap)
    card(s, x, y, cw, 1.4, fill=f)
    txt(s, x+0.25, y+0.24, cw-0.5, 0.3, h, 14, ORANGE, True)
    txt(s, x+0.25, y+0.66, cw-0.5, 0.6, d, 9.8, GRAY, line=1.2)
txt(s, 1.1, 6.15, 6.0, 0.25, "2026.07", 11, GRAY, True)
txt(s, 1.1, 6.55, 11.2, 0.3, "RAG: AI가 답을 지어내지 않고 사내 문서에서 근거를 먼저 찾아 답하는 방식 · AX: AI 기반 업무 전환", 8.2, LGRAY)

# =====================================================================
# 2. 오늘의 요약 (nav 전체 개관)
# =====================================================================
s = slide()
nav(s, None)
txt(s, 1.1, 0.92, 11.3, 0.55, "오늘, 이 세 가지만 기억하시면 됩니다", 23, DARK, True)
txt(s, 1.1, 1.52, 11.4, 0.4, "사례 → 역량 → 계획. 제품을 팔러 온 자리가 아니라, 이만큼 만드는 팀이라는 걸 보여드립니다.", 12, GRAY)
cols = [
    ("①  사례", "직접 만든 RAG", ["편람 520p 수집", "출처와 함께 답하는 AI", "팀이 직접 구현·검증"], WHITE),
    ("②  역량", "난점을 넘은 실행력", ["개발도구 없는 PC", "위키 인증·매일 바뀌는 편람", "현장 난점을 직접 해결"], CREAM),
    ("③  계획", "실도입·확장 청사진", ["사내 환경 갖춰지면 즉시 적용", "다음 확장까지 설계", "끌고 갈 역량 보유"], WHITE),
]
cw, gap, x0, y = 3.72, 0.35, 1.1, 2.15
for i, (tag, h, ds, f) in enumerate(cols):
    x = x0 + i*(cw+gap)
    card(s, x, y, cw, 3.4, fill=f)
    txt(s, x+0.3, y+0.32, cw-0.6, 0.3, tag, 15, ORANGE, True)
    txt(s, x+0.3, y+0.9, cw-0.6, 0.5, h, 18, DARK, True)
    txt(s, x+0.3, y+1.75, cw-0.6, 1.4,
        [[("· ", {'color':ORANGE,'bold':True}), (d, {'color':GRAY})] for d in ds], 11.5, GRAY, line=1.5)
band(s, "제품을 파는 자리가 아닙니다. ITO팀이 이만큼 만들 수 있는 팀이라는 걸 보여드리는 자리입니다.")
footer(s, 2)

# =====================================================================
# 3. [배경]
# =====================================================================
s = slide()
header(s, 0, "상담의 병목은 사람이 아니라 '흩어진 지식'입니다",
       "제도·상품이 자주 바뀌는 증권 상담 — 정작 시간을 잡아먹는 건 '지식을 찾는 방식'")
probs = [
    ("분산된 지식", ["편람·위키·공지·메신저가 흩어짐", "필요한 내용까지 검색 경로가 김"]),
    ("변경 반영 시차", ["제도·상품·수수료 변경", "현장 숙지까지 시차 → 오안내 위험"]),
    ("응대 편차", ["숙련도에 따라 검색어·표현·누락이 다름", "상담 품질이 들쭉날쭉"]),
]
cw, gap, x0, y = 3.72, 0.35, 1.1, 2.15
for i, (h, ds) in enumerate(probs):
    x = x0 + i*(cw+gap)
    card(s, x, y, cw, 2.3)
    txt(s, x+0.3, y+0.28, 0.6, 0.4, "0"+str(i+1), 20, ORANGE, True)
    txt(s, x+0.3, y+0.82, cw-0.6, 0.35, h, 15, DARK, True)
    txt(s, x+0.3, y+1.28, cw-0.6, 0.9,
        [[("· ", {'color':ORANGE,'bold':True}), (d, {'color':GRAY})] for d in ds], 11, GRAY, line=1.4)
rrect(s, 1.1, 4.62, 11.4, 0.6, CREAM, linecol=BORDER, radius=0.08)
txt(s, 1.35, 4.62, 11.0, 0.6, [[("▶  상담 현장 영상   ", {'color':ORANGE,'bold':True,'size':12}),
    ("지금 상담원이 겪는 상황을 먼저 보여드린 뒤, 우리가 만든 화면으로 이어집니다.", {'color':GRAY,'size':11})]],
    11, GRAY, anchor=MSO_ANCHOR.MIDDLE)
band(s, "문제는 상담원이 아니라, 지식을 찾는 '방식'입니다.")
footer(s, 3)

# =====================================================================
# 4. [만든 것] 솔루션 개요
# =====================================================================
s = slide()
header(s, 1, "우리가 만든 것 — 세 가지 일을 하나로",
       "단일 데모가 아니라, 상담 현장에 실제로 필요한 세 가지 업무를 하나의 도구로")
sol = [
    ("답변 검색", ["질문에 필요한 답·근거 즉시", "추천 응대 멘트 + 출처 링크"]),
    ("업무편람 RAG", ["절차·예외 기준·처리 방법", "출처(문서·페이지)와 함께 제공"]),
    ("신입 교육 (AI 코치)", ["AI 고객과 대화 → 즉시 채점", "모범답안 제시 (페르소나 8종)"]),
]
cw, gap, x0, y = 3.72, 0.35, 1.1, 2.15
for i, (h, ds) in enumerate(sol):
    x = x0 + i*(cw+gap)
    card(s, x, y, cw, 2.85)
    txt(s, x+0.3, y+0.3, 0.6, 0.4, "0"+str(i+1), 20, ORANGE, True)
    txt(s, x+0.3, y+0.86, cw-0.6, 0.35, h, 15.5, DARK, True)
    txt(s, x+0.3, y+1.4, cw-0.6, 1.2,
        [[("· ", {'color':ORANGE,'bold':True}), (d, {'color':GRAY})] for d in ds], 11.5, GRAY, line=1.45)
band(s, "처음엔 상담원의 내부 보조 도구로. 성능·보안·운영이 검증되면 접점을 넓혀갑니다.")
footer(s, 4)

# =====================================================================
# 5. [만든 것] 데이터 전처리 (간단히)
# =====================================================================
s = slide()
header(s, 1, "편람을 'AI가 찾을 수 있는 형태'로 바꿉니다",
       "통째로 넣지 않습니다. '찾아지는 카드 묶음'으로 바꿔 두는 것이 핵심")
steps = [
    ("위키·문서 수집", "흩어진 원문을 모음"),
    ("조각으로 나누기", "의미 단위로 자름"),
    ("의미로 색인", "AI가 '뜻'으로 찾게"),
    ("출처와 함께 저장", "어디서 왔는지 부착"),
]
cw, gap, x0, y = 2.55, 0.45, 1.15, 2.45
for i, (h, d) in enumerate(steps):
    x = x0 + i*(cw+gap)
    card(s, x, y, cw, 1.85)
    txt(s, x+0.25, y+0.26, 0.6, 0.4, "0"+str(i+1), 18, ORANGE, True)
    txt(s, x+0.25, y+0.8, cw-0.5, 0.35, h, 13.5, DARK, True)
    txt(s, x+0.25, y+1.2, cw-0.5, 0.4, d, 10, GRAY)
    if i < 3:
        txt(s, x+cw+0.02, y+0.58, 0.42, 0.6, "→", 20, LGRAY, True, align=PP_ALIGN.CENTER)
txt(s, 1.15, 4.6, 11.3, 0.5, [[("여기에 더해, ", {'color':GRAY,'size':12}),
    ("답변 정확도를 높이는 우리만의 장치", {'color':ORANGE,'bold':True,'size':12}),
    ("를 얹었습니다 (뒤 '어려웠던 점'에서 설명)", {'color':GRAY,'size':12})]], 12, GRAY)
band(s, "편람을 통째로 저장하지 않고, '검색되는 카드 묶음'으로 바꿔 둡니다.")
footer(s, 5)

# =====================================================================
# 6. [어려웠던 점] 개요
# =====================================================================
s = slide()
header(s, 2, "만들면서 부딪힌 어려웠던 점 — 그리고 해결",
       "편람을 AI가 읽게 만드는 길의 난점 — 고객사 폐쇄망 환경에도 똑같이 존재합니다")
walls = [
    ("①", "닫힌 회사 환경", ["개발도구·자동 로그인 없음", "데이터를 어떻게 가져오나"]),
    ("②", "매일 바뀌는 편람", ["조금씩 바뀌는 내용", "매번 전부 다시 하지 않고 갱신"]),
    ("③", "정확한 답과 근거", ["엉뚱한 답 차단·종목코드 검색", "'왜 그 답인지' 근거 부착"]),
    ("④", "외부 AI 의존", ["지금은 외부 AI", "사내 AI로 갈아끼울 준비"]),
]
cw, gap, x0, y = 2.78, 0.24, 0.94, 2.15
for i, (n, h, ds) in enumerate(walls):
    x = x0 + i*(cw+gap)
    card(s, x, y, cw, 3.2, fill=(CREAM if i==3 else WHITE))
    txt(s, x+0.28, y+0.28, 0.6, 0.35, n, 16, ORANGE, True)
    txt(s, x+0.28, y+0.82, cw-0.56, 0.65, h, 14.5, DARK, True, line=1.1)
    txt(s, x+0.28, y+1.65, cw-0.56, 1.4,
        [[("· ", {'color':ORANGE,'bold':True}), (d, {'color':GRAY})] for d in ds], 10.5, GRAY, line=1.4)
band(s, "모두 폐쇄망 금융사라면 똑같이 만나는 난점입니다. 우리는 이미 하나씩 해결했습니다.")
footer(s, 6)

# =====================================================================
# 어려웠던 점 상세 공통 렌더러 (문제 → 해결, 개조식)
# =====================================================================
def detail(page, title, subtitle, blocks, note=None, band_txt=""):
    s = slide()
    header(s, 2, title, subtitle)
    cw, gap, x0, y, ch = 5.6, 0.45, 1.1, 2.1, 2.75
    for i, (prob, sol) in enumerate(blocks):
        x = x0 + i*(cw+gap)
        card(s, x, y, cw, ch)
        txt(s, x+0.32, y+0.26, cw-0.64, 0.75,
            [[("어려웠던 점  ", {'color':ORANGE,'bold':True,'size':10.5}), (prob, {'color':DARK,'bold':True,'size':12.5})]],
            12.5, DARK, line=1.25)
        txt(s, x+0.32, y+1.2, cw-0.64, ch-1.35,
            [[("해결  ", {'color':GREEN,'bold':True,'size':10.5}), (sol, {'color':GRAY,'size':11})]],
            11, GRAY, line=1.4)
    if note:
        txt(s, 1.1, 5.55, 11.4, 0.4, [[("↳ ", {'color':ORANGE,'bold':True,'size':10.5}), (note, {'color':LGRAY,'size':10.5})]], 10.5, LGRAY, line=1.25)
    band(s, band_txt)
    footer(s, page)

# 7. 어려웠던 점 ①
detail(7, "어려웠던 점 ① — 닫힌 회사 환경에서 데이터 가져오기",
    "핵심 질문: '사내에만 있는 업무편람 데이터를 어떻게 가져오나?'",
    [
     ("사내망에서만 위키 접근 가능 — 그 PC엔 개발 도구를 깔 수 없음",
      "'꺼내는 일'과 '가공하는 일'을 다른 컴퓨터로 분리. 금고에선 서류만 꺼내고, 정리는 밖에서 하는 방식."),
     ("AI가 위키에 접근하려면 매번 사람이 로그인",
      "이미 로그인된 Windows 계정을 신분증처럼 활용 → 무인 접속. 매일 바뀌는 인증번호도 무관."),
    ],
    note="화면에 접혀 있던 페이지까지 빠짐없이 수집 — 편람 누락 0건",
    band_txt="고객사도 똑같은 폐쇄망 환경입니다. 우리는 이미 넘어온 길입니다.")

# 8. 어려웠던 점 ②
detail(8, "어려웠던 점 ② — 매일 조금씩 바뀌는 편람 따라잡기",
    "편람은 매일 조금씩 바뀜 — 매번 전부 다시 처리하면 시간·비용 감당 불가",
    [
     ("어디가 바뀌었는지 모르면, 매번 편람 전체를 처음부터 재처리",
      "문서마다 '지문(내용 표시)'을 찍어두고 바뀐 문서만 재처리. 오타 한 줄에 책 전체를 재인쇄하지 않고, 그 페이지만 교체하는 방식."),
     ("상담원은 늘 최신 내용을 봐야 신뢰 가능",
      "매일 자동으로 변경분만 반영 → 항상 최신 상태. 불필요한 재처리 제거."),
    ],
    band_txt="규정이 수시로 바뀌는 증권 업무에 맞는 방식입니다. 바뀐 만큼만, 자동으로.")

# 9. 어려웠던 점 ③
detail(9, "어려웠던 점 ③ — 정확한 답, 그리고 '왜 그 답인지'",
    "발표에서 가장 궁금해하실 지점 — 답이 정확한가, 그 근거를 댈 수 있는가",
    [
     ("'K-OTC' 같은 종목코드·고유명사를 '뜻'으로만 찾으면 놓침",
      "'뜻으로 찾기' + '단어로 찾기'를 함께 사용. 두 방식을 겹치자 검색 정확도가 눈에 띄게 상승."),
     ("AI가 가끔 그럴듯하지만 엉뚱한 답을 내놓음",
      "모든 답에 근거 문서·페이지 부착 → 답보다 '근거'를 먼저 확인. 틀려도 어디서 왔는지 즉시 추적."),
    ],
    note="평가에서 정답 문서가 항상 상위 3건 안에 포함됨을 확인 (문항 확대 검증 중)",
    band_txt="근거 없는 답은 내지 않습니다. AI가 아니라 상담원이 최종 판단합니다.")

# 10. 어려웠던 점 ④
detail(10, "어려웠던 점 ④ — 지금은 외부 AI, 그러나 사내 AI로 갈 준비",
    "사내에서 AI를 돌릴 환경이 아직 없음 — 안전하게, 그리고 나중에 교체 가능하게",
    [
     ("사내에 AI 구동 환경(GPU 등) 부재 → 외부 AI에 의존",
      "고객 데이터는 미사용, 나가는 데이터는 로그로 기록. 문서 '찾기'(임베딩)는 이미 사내 모델로 전환 완료."),
     ("나중에 사내 AI 도입 시 시스템을 다시 만들어야 하나?",
      "'모델만 갈아끼우면' 되도록 교체 계층을 미리 설계. 사내망에 AI가 들어오는 즉시 전환."),
    ],
    band_txt="외부에 의존하는 지금도, 사내로 들어갈 다음도 — 둘 다 준비돼 있습니다.")

# =====================================================================
# 11. [시연]
# =====================================================================
s = slide()
header(s, 3, "시연 — 답을 찾는 AI, 사람을 키우는 AI",
       "개념이 아니라 실제로 동작하는 화면 (기존 5분 발표 영상 활용)")
demo = [
    ("응대 모드 — 상담원 Copilot", ["두서없는 질문도 근거를 먼저 검색", "정리된 답변 + 추천 응대 멘트"], "모든 답변 출처 부착 · 신뢰도 상/중/하"),
    ("AI 코치 모드 — 즉시 채점", ["AI가 8종 고객으로 질문", "신입 응대 → 점수·누락·모범답안 즉시"], "페르소나 8종 · 난이도 3단계 · 약점 복습"),
]
cw, gap, x0, y = 5.6, 0.45, 1.1, 2.1
for i, (h, ds, tag) in enumerate(demo):
    x = x0 + i*(cw+gap)
    card(s, x, y, cw, 2.5, fill=(CREAM if i==0 else WHITE))
    txt(s, x+0.32, y+0.28, cw-0.64, 0.35, h, 15.5, DARK, True)
    txt(s, x+0.32, y+0.82, cw-0.64, 0.9,
        [[("· ", {'color':ORANGE,'bold':True}), (d, {'color':GRAY})] for d in ds], 11.5, GRAY, line=1.5)
    txt(s, x+0.32, y+1.95, cw-0.64, 0.4, tag, 10.5, ORANGE, True)
rrect(s, 1.1, 4.82, 11.4, 0.55, WHITE, linecol=BORDER, radius=0.08)
txt(s, 1.35, 4.82, 11.0, 0.55, [[("▶  우리가 만든 화면   ", {'color':ORANGE,'bold':True,'size':12}),
    ("실제 질문을 던지면 근거와 함께 답이 나오는 과정을 영상으로.", {'color':GRAY,'size':11})]],
    11, GRAY, anchor=MSO_ANCHOR.MIDDLE)
band(s, "편람을 찾아줄 뿐 아니라 응대 멘트까지 — 신입은 선배 없이도 반복 훈련으로 숙련됩니다.")
footer(s, 11)

# =====================================================================
# 12. [도입·비전] 기대효과 (정성)
# =====================================================================
s = slide()
header(s, 4, "이걸로 무엇이 좋아지나 — 세 가지",
       "숫자로 겁주는 자리가 아닙니다. 무엇이 어떻게 나아지는지를 먼저")
eff = [
    ("응대 시간 단축", ["지식 탐색 시간 감소", "고객 대기·상담원 부담 ↓"]),
    ("답변 품질 표준화", ["누가 응대해도 같은 근거", "숙련도 편차·오안내 위험 ↓"]),
    ("신입 교육 가속", ["AI 코치로 반복 훈련", "선배 없이도 빠른 숙련"]),
]
cw, gap, x0, y = 3.72, 0.35, 1.1, 2.15
for i, (h, ds) in enumerate(eff):
    x = x0 + i*(cw+gap)
    card(s, x, y, cw, 2.5, fill=(CREAM if i==1 else WHITE))
    txt(s, x+0.3, y+0.3, 0.6, 0.4, "0"+str(i+1), 20, ORANGE, True)
    txt(s, x+0.3, y+0.86, cw-0.6, 0.35, h, 15.5, DARK, True)
    txt(s, x+0.3, y+1.35, cw-0.6, 0.9,
        [[("· ", {'color':ORANGE,'bold':True}), (d, {'color':GRAY})] for d in ds], 11.5, GRAY, line=1.45)
txt(s, 1.1, 4.85, 11.4, 0.4, "정량 효과(절감 시간·비용 등)는 별도 근거 자료로 준비 — 필요 시 공유(부록 B)", 10.5, LGRAY)
band(s, "핵심은 '사람을 줄이는 것'이 아니라, 같은 인력으로 더 빠르고·정확하게·많이 해내는 것입니다.")
footer(s, 12)

# =====================================================================
# 13. [도입·비전] 실도입 청사진
# =====================================================================
s = slide()
header(s, 4, "실제 도입한다면 — 이렇게 올립니다",
       "지금 당장은 아니어도, 도입이 결정되면 바로 올릴 수 있는 그림")
layers = [
    ("상담원 화면", "질문 입력\n답·근거 확인"),
    ("서비스(API)", "권한·세션\n관리"),
    ("검색·답변(RAG)", "근거 검색\n답 구성"),
    ("지식 저장소", "기업용 벡터 DB\n안전 보관"),
    ("AI 모델", "사내 모델로\n교체"),
]
cw, gap, x0, y = 2.15, 0.28, 1.1, 2.35
for i, (h, d) in enumerate(layers):
    x = x0 + i*(cw+gap)
    card(s, x, y, cw, 1.9, fill=(CREAM if i in (3,4) else WHITE))
    txt(s, x+0.2, y+0.3, cw-0.4, 0.65, h, 13, DARK, True, align=PP_ALIGN.CENTER, line=1.05)
    txt(s, x+0.2, y+1.0, cw-0.4, 0.75, d, 9.5, GRAY, align=PP_ALIGN.CENTER, line=1.2)
    if i < 4:
        txt(s, x+cw-0.02, y+0.68, 0.32, 0.5, "→", 16, LGRAY, True, align=PP_ALIGN.CENTER)
txt(s, 1.1, 4.55, 11.4, 0.5, [[("PoC에선 가벼운 도구로 검증. ", {'color':GRAY,'size':11.5}),
    ("실서비스는 별도 서버 + 기업용 벡터 DB", {'color':ORANGE,'bold':True,'size':11.5}),
    ("로 올려 안정성·보안 확보.", {'color':GRAY,'size':11.5})]], 11.5, GRAY, line=1.3)
band(s, "화면·서비스·검색·저장소·모델을 분리 — 나중에 '답변 모델'만 사내용으로 갈아끼웁니다.")
footer(s, 13)

# =====================================================================
# 14. [도입·비전] 앞으로의 계획 / 비전
# =====================================================================
s = slide()
header(s, 4, "앞으로의 계획 — 확장의 청사진",
       "더 개발하겠다는 게 아니라, 실제 도입 시 무엇이 필요한지를 제시")
txt(s, 1.1, 2.0, 5.4, 0.3, "적용 범위는 이렇게 넓어집니다", 13, DARK, True)
stages = [
    ("지금 · 업무편람", "출처 기반 검색·답변  ✅ 구현·검증 완료"),
    ("다음 · 사내 문서 통합", "게시판·파일서버·PDF까지 같은 방식"),
    ("비전 · 개인별 지식 허브", "메일·메신저·회의록까지 묶는 허브"),
]
y = 2.5
for i, (h, d) in enumerate(stages):
    card(s, 1.1, y, 5.3, 0.92, fill=(CREAM if i==0 else WHITE))
    txt(s, 1.35, y+0.16, 0.5, 0.5, "0"+str(i+1), 17, ORANGE, True)
    txt(s, 1.95, y+0.15, 4.3, 0.3, h, 12.5, DARK, True)
    txt(s, 1.95, y+0.5, 4.3, 0.3, d, 10, GRAY)
    y += 1.08
txt(s, 6.9, 2.0, 5.6, 0.3, "실도입에 필요한 것 (우리가 제시합니다)", 13, DARK, True)
needs = [
    ("사내 AI 환경", "AI를 돌릴 사내 GPU 서버"),
    ("기업용 벡터 DB", "PoC 경량 저장소 → 운영용 기업 DB"),
    ("국산 금융 LLM 전환", "데이터 주권·규제 대응"),
]
y = 2.5
for i, (h, d) in enumerate(needs):
    card(s, 6.9, y, 5.6, 0.92)
    txt(s, 7.15, y+0.15, 5.1, 0.3, h, 12.5, DARK, True)
    txt(s, 7.15, y+0.5, 5.1, 0.3, d, 10, GRAY)
    y += 1.08
txt(s, 6.9, 5.72, 5.6, 0.28, "타 증권사도 이미 같은 방향으로 가고 있습니다.", 10, ORANGE, True)
band(s, "이 프로젝트를 끌고 갈 역량이 우리에게 있다 — 그것을 오늘 보여드렸습니다.", t=6.12, h=0.58)
footer(s, 14)

# =====================================================================
# 15. Q&A
# =====================================================================
s = slide()
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
bg.fill.solid(); bg.fill.fore_color.rgb = DARK; bg.line.fill.background(); bg.shadow.inherit=False
txt(s, 1.1, 2.7, 11.0, 1.2, "Q&A", 54, ORANGE, True)
txt(s, 1.15, 3.95, 11.0, 0.5, "Thank you", 22, WHITE, False)
txt(s, 1.15, 4.6, 11.0, 0.3, KICK, 11, FAINT)

# =====================================================================
# 16. 부록 구분
# =====================================================================
s = slide()
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
bg.fill.solid(); bg.fill.fore_color.rgb = DARK; bg.line.fill.background(); bg.shadow.inherit=False
txt(s, 1.1, 3.0, 11.0, 0.8, "부록 · 질문 대비 백업", 30, WHITE, True)
txt(s, 1.15, 3.9, 11.0, 0.4, "발표 본편에서는 넘어가고, 질문이 나올 때만 펼치는 근거 자료입니다.", 13, FAINT)

def appx_header(s, title, subtitle):
    txt(s, 1.1, 0.5, 8.0, 0.3, "부록", 11, ORANGE, True)
    txt(s, 1.1, 0.86, 11.3, 0.55, title, 22, DARK, True)
    if subtitle: txt(s, 1.1, 1.46, 11.4, 0.4, subtitle, 12, GRAY)

# 17. 부록 A
s = slide()
appx_header(s, "부록 A · 답변을 정확하게 만든 방법", "기본 검색이 놓치는 것을, 네 가지 신호를 겹쳐 메웠습니다.")
sig = [
    ("제목·본문 함께 보기", ["표제어는 제목이", "풀어쓴 질문은 본문이 포착"]),
    ("같은 뜻 여러 번 묻기", ["여러 표현으로 질의", "하나라도 명중하면 채택"]),
    ("뜻으로 + 단어로 찾기", ["의미 검색 + 키워드 검색", "종목코드·고유명사 포착"]),
    ("사내 용어 사전", ["'예수금=고객예탁금'", "사전 한 줄로 즉시 반영"]),
]
cw, gap, x0, y = 2.78, 0.24, 0.94, 2.05
for i, (h, ds) in enumerate(sig):
    x = x0 + i*(cw+gap)
    card(s, x, y, cw, 2.95)
    txt(s, x+0.26, y+0.26, 0.6, 0.35, "0"+str(i+1), 16, ORANGE, True)
    txt(s, x+0.26, y+0.78, cw-0.52, 0.6, h, 13, DARK, True, line=1.1)
    txt(s, x+0.26, y+1.55, cw-0.52, 1.2,
        [[("· ", {'color':ORANGE,'bold':True}), (d, {'color':GRAY})] for d in ds], 10, GRAY, line=1.4)
band(s, "네 신호를 겹친 결과, 평가 문항에서 정답이 항상 상위 3건 안에 들어왔습니다.")
footer(s, "A")

# 18. 부록 B
s = slide()
appx_header(s, "부록 B · 정량 근거 수치", "본편에선 굳이 내세우지 않되, 물어보시면 바로 답할 수 있는 근거들")
stats = [
    ("업무편람 수집", "520p", "누락 0건"),
    ("적재 조각 수", "1,281", "의미 단위 색인"),
    ("검색 정확도", "상위 3건 내", "정답 항상 포함"),
    ("출처 부착률", "100%", "모든 답변에"),
    ("재처리 절감", "변경분만", "매일 자동 갱신"),
]
cw, gap, x0, y = 2.15, 0.28, 1.1, 2.2
for i, (h, v, d) in enumerate(stats):
    x = x0 + i*(cw+gap)
    card(s, x, y, cw, 2.1)
    txt(s, x+0.2, y+0.28, cw-0.4, 0.3, h, 11, GRAY, True, align=PP_ALIGN.CENTER)
    txt(s, x+0.2, y+0.72, cw-0.4, 0.55, v, 20, ORANGE, True, align=PP_ALIGN.CENTER)
    txt(s, x+0.2, y+1.45, cw-0.4, 0.4, d, 10, GRAY, align=PP_ALIGN.CENTER)
txt(s, 1.1, 4.6, 11.4, 0.6,
    "※ 답변 생성 정확도는 30문항 기준 측정값 — 문항을 늘려 검증 확대 중. "
    "억원·ROI 등 비용 효과 수치는 산정 근거와 함께 별도 자료로 보관.", 10, LGRAY, line=1.3)
band(s, "수치는 '증명'을 위한 근거일 뿐, 오늘의 메시지는 '이만큼 만드는 팀'입니다.")
footer(s, "B")

# 19. 부록 C
s = slide()
appx_header(s, "부록 C · 타 금융사 RAG 도입 현황", "검증 안 된 실험이 아니라, 업계가 이미 가는 방향을 우리가 직접 구현")
refs = [
    ("하나은행 H-GPT", "검색·AI 모드 + 규정 RAG + 출처 표시 (우리와 UX 사실상 동일)"),
    ("한국은행 BOKI", "완전 폐쇄망, 내부문서 140만건 (폐쇄망 선례의 최상위 근거)"),
    ("신한·미래에셋·키움·한투·IBK", "증권사 RAG 챗봇 온프레미스 도입 중 (국산 sLLM 포함)"),
    ("일본 MUFG·미즈호·SMBC", "사내 AI로 대규모 문서 검색·업무 시간 절감"),
]
y = 2.05
for i, (h, d) in enumerate(refs):
    card(s, 1.1, y, 11.4, 0.82, fill=(CREAM if i<2 else WHITE))
    txt(s, 1.35, y, 3.9, 0.82, h, 12.5, DARK, True, anchor=MSO_ANCHOR.MIDDLE, line=1.05)
    txt(s, 5.4, y, 6.9, 0.82, d, 11, GRAY, anchor=MSO_ANCHOR.MIDDLE, line=1.15)
    y += 0.95
band(s, "'검증된 방향을 벤더가 아니라 ITO팀이 직접 만들었다' — 그것이 차별점입니다.")
footer(s, "C")

out = "/home/user/2026_HICT_ChatBot/docs/presentation/증권 발표용/HICT_PPT_15min_신규.pptx"
prs.save(out)
print("saved:", out)
print("slides:", len(prs.slides._sldIdLst))
