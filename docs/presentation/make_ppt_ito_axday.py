# -*- coding: utf-8 -*-
"""ITO AX Day 15분 테크데이 발표용 .pptx 생성기 — "상담원 AI 코치".

목적:
  한화투자증권 ITO팀의 사내 AX Day(15분) 발표용 슬라이드를 생성한다.
  주제는 "증권 상담원 AI 코치" RAG 챗봇 PoC. 비IT 청중 배려 — IT 용어를 노출하지
  않고 직관적 단어로만 서술한다.

실행:
  cd /home/user/2026_HICT_ChatBot && python3 docs/presentation/make_ppt_ito_axday.py

산출물:
  docs/presentation/ITO_AX_Day_상담원AI코치.pptx  (본편 18 + 부록 4 = 총 22장)
  ※ 본편 18에는 신규 슬라이드 10.5(시스템 아키텍처, s10p5_architecture) 포함.
  ※ 슬라이드 5(데이터 흐름)·10.5(아키텍처)는 아키텍쳐/*.html 을 headless Chrome으로
     PNG 렌더링해 삽입한다(html_to_png 헬퍼). Selenium + Chrome 필요.

디자인:
  "에르메스 × 한화" — 웜페이퍼(CREAM) 배경, 오렌지 강조, 세리프(Georgia) 숫자.
  넓은 여백 / 얇은 규칙선 / 그림자 없음 / 절제된 카드.

근거 문서(슬라이드별 주석에 개별 명시):
  - README.md (성공 기준), docs/ANSWER_QUALITY.md (정확도 근거),
  - docs/adr/0001·0002·0003·0004·0010 (설계 결정),
  - docs/api-spec.md (하이브리드 검색), tests/test_questions.json (30문항),
  - docs/CRAWLER_GUIDE.md, connectors/confluence_crawl.py (폐쇄망 수집),
  - docs/ONPREM_ROADMAP.md (온프렘 로드맵).

기법 출처(복붙 아님, 헬퍼 패턴만 이식):
  - docs/presentation/make_ppt_hanwha_poc.py 1~210줄: _ea/put_text/rect/shape_text/slide/header/takeaway
  - docs/presentation/증권 발표용/build_hict_customer.py 126~256줄: add_movie + _set_video_autoplay

정직성 3대 가드:
  (1) 정확도 "100문항 측정" 창작 금지 — 100문항은 '재측정 예정'(계획)일 뿐. 측정치는 30문항 기준.
  (2) MCP(표준 연동)는 현재 코드 미적용 → '향후 활용 여지'로만 표기.
  (3) 타 증권사 수치·회사명·금액 창작 절대 금지 → '자료 반영 예정' 자리표시만.
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
import os

# ── 경로/임시폴더 ────────────────────────────────────────────────
# 스크립트가 있는 폴더의 절대경로. 아키텍처 HTML·임시 PNG 모두 이 기준으로 잡는다.
_HERE = os.path.dirname(os.path.abspath(__file__))
# 아키텍처 다이어그램 HTML 폴더 (docs/presentation/아키텍쳐/*.html)
_ARCH_DIR = os.path.join(_HERE, "아키텍쳐")
# HTML→PNG 변환 결과를 담는 임시 폴더 (디버깅을 위해 종료 후에도 보관)
_TMP_DIR = os.path.join(_HERE, "tmp")


def ensure_tmp():
    """스크립트 시작 시 임시 PNG 폴더를 생성한다(절대경로). 이미 있으면 그대로 둔다."""
    os.makedirs(_TMP_DIR, exist_ok=True)
    return _TMP_DIR


def html_to_png(html_path, output_png_path, width=1360, height=900):
    """로컬 HTML(SVG 포함)을 headless Chrome으로 렌더링해 PNG로 저장한다.

    - Selenium 4의 내장 Selenium Manager가 chromedriver를 자동 확보하므로
      별도 드라이버 설치가 필요 없다(환경: selenium 4.29, Chrome 설치됨).
    - .page 요소의 실제 콘텐츠 크기에 맞춰 창을 키운 뒤 그 요소만 캡처 →
      여백 없이 다이어그램 전체가 담긴다. force-device-scale-factor=2로 2배 선명도.
    - 성공 시 output_png_path(절대경로) 반환, 실패 시 None 반환 + 경고 출력.
      (연관: s05_flow / s10p5_architecture 에서 이 반환값으로 이미지/자리표시 분기)

    width/height 인자는 초기 창 크기 힌트로만 사용하고, 최종 크기는 콘텐츠에 맞춘다.
    """
    if not os.path.exists(html_path):
        print(f"  [경고] HTML 없음 → 자리표시로 대체: {html_path}")
        return None
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        import time

        url = "file:///" + os.path.abspath(html_path).replace("\\", "/")
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--hide-scrollbars")
        opts.add_argument("--force-device-scale-factor=2")  # 2배 해상도로 선명하게
        opts.add_argument(f"--window-size={width},{height}")
        drv = webdriver.Chrome(options=opts)
        try:
            drv.get(url)
            time.sleep(0.8)  # 웹폰트/SVG 레이아웃 안정화 대기
            # 콘텐츠 실제 크기 측정 후 창을 그 크기로 맞춘다(.page 없으면 body 기준)
            sel = ".page" if drv.execute_script(
                "return !!document.querySelector('.page')") else "body"
            cw = drv.execute_script(
                f"return document.querySelector('{sel}').scrollWidth")
            ch = drv.execute_script(
                f"return document.querySelector('{sel}').scrollHeight")
            drv.set_window_size(cw + 40, ch + 40)
            time.sleep(0.4)
            os.makedirs(os.path.dirname(os.path.abspath(output_png_path)),
                        exist_ok=True)
            drv.find_element("css selector", sel).screenshot(
                os.path.abspath(output_png_path))
        finally:
            drv.quit()
        if os.path.exists(output_png_path) and os.path.getsize(output_png_path) > 0:
            return os.path.abspath(output_png_path)
        print("  [경고] PNG 생성 실패(빈 파일) → 자리표시로 대체")
        return None
    except Exception as e:
        print(f"  [경고] HTML→PNG 변환 실패 → 자리표시로 대체: {e}")
        return None


# ── 디자인 토큰 : 에르메스 × 한화 ────────────────────────────────
ORANGE = RGBColor(0xF3, 0x73, 0x21)   # 주 강조 (한화 오렌지 = 에르메스 오렌지 톤)
ORANGED = RGBColor(0xC0, 0x5A, 0x17)  # 딥 테라코타 (헤드라인 강조/밑줄)
CREAM = RGBColor(0xF7, 0xF1, 0xE7)    # 슬라이드 배경 (에르메스 웜페이퍼)
ESPRESSO = RGBColor(0x3B, 0x2C, 0x22) # 본문 잉크 (네이비 대신 따뜻한 브라운)
TAUPE = RGBColor(0x8B, 0x7E, 0x70)    # 보조 텍스트/캡션
LINE = RGBColor(0xD8, 0xCB, 0xB8)     # 얇은 구분선/카드 테두리
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GOOD = RGBColor(0x15, 0x80, 0x3D)     # 최소 사용
BAD = RGBColor(0xB9, 0x1C, 0x1C)      # 최소 사용
FONT_KR = "맑은 고딕"                  # 본문 한글
FONT_EN = "Georgia"                   # 숫자/영문 강조에 세리프로 격조

SW, SH = Inches(13.333), Inches(7.5)  # 16:9
prs = Presentation()
prs.slide_width, prs.slide_height = SW, SH
BLANK = prs.slide_layouts[6]
_PAGE = [0]


# ── 헬퍼 ────────────────────────────────────────────────────────
def _ea(run, font):
    """한글이 라틴폰트로 깨지는 것을 막는 필수 기법 — East-Asian/Complex-Script 폰트 XML 강제.
    (출처: make_ppt_hanwha_poc.py 44~51줄 _ea 를 폰트 인자화하여 이식)"""
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = rPr.makeelement(qn(tag), {})
            rPr.append(el)
        el.set("typeface", font)


def _apply(run, size, bold, color, font):
    f = run.font
    f.name, f.size, f.bold = font, Pt(size), bold
    f.color.rgb = color
    _ea(run, font)


def _line_font(ln):
    """라인 튜플에서 폰트를 뽑는다. 6번째 원소가 있으면 그 폰트, 없으면 한글 기본."""
    return ln[5] if len(ln) > 5 else FONT_KR


def put_text(slide, x, y, w, h, lines, anchor=MSO_ANCHOR.TOP, space=4):
    """텍스트 박스. lines: [(text, size, bold, color, align[, font]), ...]"""
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for i, ln in enumerate(lines):
        text, size, bold, color, align = ln[:5]
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space)
        run = p.add_run()
        run.text = text
        _apply(run, size, bold, color, _line_font(ln))
    return box


def rect(slide, x, y, w, h, fill, line=None, round_=True, line_w=1.0):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if round_ else MSO_SHAPE.RECTANGLE, x, y, w, h)
    if round_:
        try:
            shape.adjustments[0] = 0.05
        except Exception:
            pass
    if fill is None:
        shape.fill.background()
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    if line:
        shape.line.color.rgb = line
        shape.line.width = Pt(line_w)
    else:
        shape.line.fill.background()
    shape.shadow.inherit = False   # 미학 원칙: 그림자 없음
    return shape


def shape_text(shape, lines, anchor=MSO_ANCHOR.TOP, space=5,
               ml=0.16, mt=0.12):
    tf = shape.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(ml)
    tf.margin_top = tf.margin_bottom = Inches(mt)
    for i, ln in enumerate(lines):
        text, size, bold, color, align = ln[:5]
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space)
        run = p.add_run()
        run.text = text
        _apply(run, size, bold, color, _line_font(ln))


def bg(s):
    """모든 슬라이드 배경을 CREAM 웜페이퍼로 채운다."""
    r = rect(s, 0, 0, SW, SH, CREAM, round_=False)
    # 배경은 항상 맨 뒤로
    sp = r._element
    sp.getparent().remove(sp)
    s.shapes._spTree.insert(2, sp)


def slide():
    _PAGE[0] += 1
    s = prs.slides.add_slide(BLANK)
    bg(s)
    return s


def header(s, kicker, title, title_size=26):
    """왼쪽 오렌지 얇은 세로바 + kicker(오렌지) + 제목(ESPRESSO). 우하단 페이지번호(TAUPE)."""
    rect(s, Inches(0.62), Inches(0.46), Inches(0.09), Inches(0.92), ORANGE, round_=False)
    put_text(s, Inches(0.9), Inches(0.42), Inches(11.8), Inches(0.36),
             [(kicker, 12.5, True, ORANGE, PP_ALIGN.LEFT)])
    put_text(s, Inches(0.88), Inches(0.74), Inches(11.9), Inches(0.8),
             [(title, title_size, True, ESPRESSO, PP_ALIGN.LEFT)])
    put_text(s, Inches(12.35), Inches(7.06), Inches(0.85), Inches(0.3),
             [(str(_PAGE[0]), 10, False, TAUPE, PP_ALIGN.RIGHT, FONT_EN)])


def takeaway(s, text, color=ESPRESSO, y=Inches(6.6)):
    """하단 핵심 메시지 1줄 바. 절제되게 ESPRESSO 배경 + WHITE 글씨."""
    bar = rect(s, Inches(0.62), y, Inches(12.1), Inches(0.58), color, round_=True)
    shape_text(bar, [(text, 14, True, WHITE, PP_ALIGN.CENTER)],
               anchor=MSO_ANCHOR.MIDDLE)


def card(s, x, y, w, h, fill=WHITE, line=LINE, line_w=1.0):
    """WHITE + 얇은 LINE 테두리 카드(그림자 없음)."""
    return rect(s, x, y, w, h, fill, line=line, line_w=line_w)


def placeholder(s, x, y, w, h, text):
    """우아한 자리표시 박스(점선 느낌 — TAUPE 테두리, CREAM 채움). 창작 금지 영역용."""
    box = rect(s, x, y, w, h, CREAM, line=TAUPE, line_w=1.25)
    # 점선 테두리
    ln = box.line._get_or_add_ln()
    d = ln.makeelement(qn('a:prstDash'), {'val': 'dash'})
    ln.append(d)
    shape_text(box, [(text, 13, False, TAUPE, PP_ALIGN.CENTER)],
               anchor=MSO_ANCHOR.MIDDLE)
    return box


# ── 슬라이드 1. 표지 ───────────────────────────────────────────
# 근거: 전체 컨셉(README.md 개요), 카피는 발표 기획안 기준
def s01_cover():
    s = prs.slides.add_slide(BLANK)   # 표지는 페이지번호 없이
    bg(s)
    # 오렌지 얇은 규칙선 포인트(좌측 세로 + 상단 짧은 가로)
    rect(s, Inches(1.1), Inches(2.05), Inches(0.12), Inches(2.4), ORANGE, round_=False)
    put_text(s, Inches(1.45), Inches(1.7), Inches(10), Inches(0.5),
             [("ITO AX Day", 15, True, ORANGE, PP_ALIGN.LEFT, FONT_EN)])
    put_text(s, Inches(1.42), Inches(2.25), Inches(11), Inches(1.6),
             [("상담원 AI 코치", 62, True, ESPRESSO, PP_ALIGN.LEFT)])
    put_text(s, Inches(1.45), Inches(4.05), Inches(11), Inches(0.6),
             [("상담응대를 정확하게, 상담교육을 더 효과적으로", 20, False, ORANGED, PP_ALIGN.LEFT)])
    # 하단 얇은 규칙선
    rect(s, Inches(1.45), Inches(5.55), Inches(10.4), Inches(0.012), LINE, round_=False)
    put_text(s, Inches(1.45), Inches(5.75), Inches(10), Inches(0.5),
             [("한화투자증권 ITO팀", 15, True, ESPRESSO, PP_ALIGN.LEFT)])
    put_text(s, Inches(11.0), Inches(5.72), Inches(1.2), Inches(0.5),
             [("2026", 22, True, TAUPE, PP_ALIGN.RIGHT, FONT_EN)])


# ── 슬라이드 2. [배경] 흩어진 지식 ─────────────────────────────
# 근거: 발표 기획안 '배경', 상담 현장 실태
def s02_scattered():
    s = slide()
    header(s, "배경 · 지금 상담 현장", "정보 분산 현황")
    put_text(s, Inches(0.9), Inches(1.7), Inches(11.5), Inches(0.5),
             [("상담원이 답 하나를 찾으려면 매번 세 곳을 헤맨다", 14.5, False, TAUPE, PP_ALIGN.LEFT)])
    items = [("사내 위키", "규정·절차가 잠들어 있는 곳"),
             ("공지사항", "매일 바뀌는 최신 안내"),
             ("메신저", "선배에게 물어 겨우 얻는 답")]
    gap = Inches(0.4)
    total = Inches(12.1)
    n = len(items)
    w = Emu(int((total - gap * (n - 1)) / n))
    x = Inches(0.62)
    for i, (name, desc) in enumerate(items):
        c = card(s, x, Inches(2.55), w, Inches(2.9))
        shape_text(c, [
            (str(i + 1).zfill(2), 30, True, ORANGE, PP_ALIGN.LEFT, FONT_EN),
            (name, 20, True, ESPRESSO, PP_ALIGN.LEFT),
            ("", 6, False, ESPRESSO, PP_ALIGN.LEFT),
            (desc, 13.5, False, TAUPE, PP_ALIGN.LEFT),
        ], anchor=MSO_ANCHOR.TOP, mt=0.22, ml=0.24)
        x = Emu(int(x + w + gap))
    takeaway(s, "지식은 많은데, 한 곳에 모여 있지 않다")


# ── 슬라이드 3. [배경] 문제 정의 3줄 ───────────────────────────
# 근거: 발표 기획안 '문제 정의', OJT 3~6개월 현업 관행
def s03_problem():
    s = slide()
    header(s, "배경 · 문제 정의", "주요 과제")
    rows = [("1", "찾는 데 오래", "질문 1건에 편람 검색 2~5분"),
            ("2", "답이 사람마다 다름", "상담 품질이 들쭉날쭉"),
            ("3", "신입이 익히는 데 오래", "OJT 3~6개월")]
    y = Inches(2.05)
    for num, head, desc in rows:
        c = card(s, Inches(0.62), y, Inches(12.1), Inches(1.28))
        put_text(s, Inches(0.9), y + Inches(0.16), Inches(1.4), Inches(1.0),
                 [(num, 46, True, ORANGE, PP_ALIGN.CENTER, FONT_EN)],
                 anchor=MSO_ANCHOR.MIDDLE)
        put_text(s, Inches(2.2), y + Inches(0.16), Inches(9.8), Inches(1.0),
                 [(head, 20, True, ESPRESSO, PP_ALIGN.LEFT),
                  (desc, 15, False, TAUPE, PP_ALIGN.LEFT)],
                 anchor=MSO_ANCHOR.MIDDLE, space=3)
        y = Emu(int(y + Inches(1.28) + Inches(0.18)))
    takeaway(s, "느리고, 고르지 않고, 오래 걸린다")


# ── 슬라이드 4. [개요] 두 가지 모드 ────────────────────────────
# 근거: docs/adr/0005-training-direct-fetch.md(훈련 모드), README.md(응대/코치 기능)
def s04_two_modes():
    s = slide()
    header(s, "개요 · 한 장 요약", "두 가지 기능")
    cards = [("응대 지원", "상담원이 물으면,\n편람 근거로 답하고\n출처까지 보여준다"),
             ("훈련 코치", "AI가 고객 역할로 질문하고,\n신입 답변을 채점하고\n피드백까지 준다")]
    gap = Inches(0.4)
    w = Inches(5.85)
    x = Inches(0.62)
    for i, (name, desc) in enumerate(cards):
        c = card(s, x, Inches(2.1), w, Inches(3.4),
                 fill=WHITE, line=ORANGE if i == 0 else LINE,
                 line_w=1.75 if i == 0 else 1.0)
        shape_text(c, [
            (name, 24, True, ORANGED, PP_ALIGN.LEFT),
            ("", 8, False, ESPRESSO, PP_ALIGN.LEFT),
        ] + [(l, 15, False, ESPRESSO, PP_ALIGN.LEFT) for l in desc.split("\n")],
            anchor=MSO_ANCHOR.MIDDLE, ml=0.3, space=6)
        x = Emu(int(x + w + gap))
    put_text(s, Inches(0.62), Inches(5.7), Inches(12.1), Inches(0.5),
             [("두 모드가 같은 편람 데이터를 함께 쓴다", 15, True, TAUPE, PP_ALIGN.CENTER)])
    takeaway(s, "물어보면 답하고, 답하면 채점한다", y=Inches(6.55))


# ── 슬라이드 5. [개요] 데이터 흐름 ─────────────────────────────
# 근거: backend/services/ingest.py(수집·정리·분할), docs/adr/0002(기억), api-spec.md(검색)
# 변경: 기존 chevron 5-step 다이어그램을 제거하고 아키텍쳐/_render_flow.html(3-레인
#       통합 흐름도)을 PNG로 렌더링해 중앙에 삽입한다. HTML 없음·변환 실패 시 자리표시.
#       (연관: html_to_png 헬퍼로 렌더 → 실패 시 placeholder() 로 폴백)
def s05_flow():
    s = slide()
    header(s, "개요 · 데이터가 흐르는 길", "데이터 파이프라인")
    # HTML → PNG 변환 (아키텍쳐/_render_flow.html)
    flow_html = os.path.join(_ARCH_DIR, "_render_flow.html")
    flow_png = os.path.join(_TMP_DIR, "flow.png")
    png = html_to_png(flow_html, flow_png, width=1420, height=760)
    # 이미지 삽입 영역: 약 11인치 × 5.5인치, 슬라이드 가로 중앙
    iw, ih = Inches(11.6), Inches(5.5)
    ix = Emu(int((SW - iw) / 2))
    iy = Inches(1.7)
    if png:
        # 실제 비율에 맞춰 폭 기준으로 넣고, 높이는 add_picture가 자동 계산.
        # 흐름도는 가로로 넓으므로 폭(iw)을 우선 맞춘다.
        pic = s.shapes.add_picture(png, ix, iy, width=iw)
        # 세로가 영역보다 크면 세로 기준으로 다시 맞춰 넘침 방지
        if pic.height > ih:
            pic._element.getparent().remove(pic._element)
            pic = s.shapes.add_picture(png, ix, iy, height=ih)
            pic.left = Emu(int((SW - pic.width) / 2))
        # 이미지가 위쪽에 붙도록 소폭 상향 정렬(중앙 y 재계산)
        pic.top = Inches(1.7)
    else:
        placeholder(s, ix, iy, iw, ih,
                    "데이터 흐름도 — 아키텍쳐/_render_flow.html 렌더 실패")
    takeaway(s, "흩어진 편람을 AI가 꺼내 쓸 수 있는 형태로")


# ── 슬라이드 6. [개요] 기본 + 플러스 알파 ──────────────────────
# 근거: docs/adr/0002-chromadb-dual-collection.md(제목·본문 분리),
#        docs/adr/0003-multi-title-max-pooling.md, api-spec.md(하이브리드), 0004(출처 먼저)
def s06_plus_alpha():
    s = slide()
    header(s, "개요 · 우리가 더한 것", "핵심 기술")
    # 좌: 기본
    c = card(s, Inches(0.62), Inches(2.05), Inches(4.0), Inches(3.5), fill=WHITE, line=LINE)
    shape_text(c, [
        ("기본", 20, True, TAUPE, PP_ALIGN.LEFT),
        ("", 10, False, ESPRESSO, PP_ALIGN.LEFT),
        ("질문과 비슷한 문서를\n찾아 답한다", 15, False, ESPRESSO, PP_ALIGN.LEFT),
    ], anchor=MSO_ANCHOR.MIDDLE, ml=0.28)
    # 우: 플러스 알파 3개
    plus = [("제목과 본문을 따로 기억", "헷갈리는 질문도 정확히"),
            ("뜻으로도, 정확한 단어로도 함께 찾기", "놓치는 답 줄임"),
            ("근거(출처)를 답보다 먼저 보여주기", "믿고 쓴다")]
    x0 = Inches(4.95)
    ph = Inches(1.05)
    y = Inches(2.05)
    put_text(s, x0, Inches(1.55), Inches(7.8), Inches(0.4),
             [("우리가 더한 플러스 알파", 15, True, ORANGED, PP_ALIGN.LEFT)])
    for head, desc in plus:
        c2 = card(s, x0, y, Inches(7.77), ph, fill=WHITE, line=ORANGE, line_w=1.25)
        put_text(s, x0 + Inches(0.28), y, Inches(7.2), ph,
                 [(head, 15, True, ESPRESSO, PP_ALIGN.LEFT),
                  (desc, 12.5, False, TAUPE, PP_ALIGN.LEFT)],
                 anchor=MSO_ANCHOR.MIDDLE, space=2)
        y = Emu(int(y + ph + Inches(0.18)))
    takeaway(s, "정보제공(RAG)을 더 정확하게, 신뢰를 더했다")


# ── 슬라이드 7~10. [문제점 해결] 벽 N 동일 템플릿 ─────────────
def wall_slide(n, kicker, title, problem, solved, ops, tk):
    """벽 N 공통 템플릿: 상단 큰 '벽 N' + 제목, 3단 카드.
    스토리: 문제 → 해결(우리가 실제로 한 것) → 실제 운영 적용 시(이렇게·이런 환경 필요).
    '해결'을 ORANGE로 강조(우리 역량), '실제 운영 적용 시'는 차분한 톤(미래·필요 환경)."""
    s = slide()
    header(s, kicker, title)
    # 상단 큰 '벽 N' 워터마크 느낌(우측)
    put_text(s, Inches(9.3), Inches(0.5), Inches(3.4), Inches(1.0),
             [(f"벽 {n}", 40, True, LINE, PP_ALIGN.RIGHT, FONT_EN)])
    cols = [("문제", problem, TAUPE, LINE, ESPRESSO),
            ("해결", solved, ORANGED, ORANGE, ESPRESSO),
            ("실제 운영 적용 시", ops, ORANGED, LINE, ESPRESSO)]
    gap = Inches(0.35)
    total = Inches(12.1)
    w = Emu(int((total - gap * 2) / 3))
    x = Inches(0.62)
    for label, body, lab_col, brd, body_col in cols:
        strong = (label == "해결")
        c = card(s, x, Inches(2.15), w, Inches(3.5),
                 fill=WHITE, line=brd, line_w=1.75 if strong else 1.0)
        shape_text(c, [
            (label, 16, True, lab_col, PP_ALIGN.LEFT),
            ("", 8, False, ESPRESSO, PP_ALIGN.LEFT),
            (body, 15 if strong else 14, strong, body_col, PP_ALIGN.LEFT),
        ], anchor=MSO_ANCHOR.TOP, ml=0.26, mt=0.24, space=6)
        x = Emu(int(x + w + gap))
    takeaway(s, tk)


# 근거: docs/CRAWLER_GUIDE.md, connectors/confluence_crawl.py, scripts/wiki_fetch.ps1
def s07_wall1():
    wall_slide(
        1, "문제 돌파 · 벽 1/4", "인터넷이 막힌 폐쇄망",
        "사내 편람을 밖으로\n내보낼 수 없다",
        "사내 인증으로 위키·편람을\n폐쇄망 안에서 직접 수집\n(PDF·HTML 반입도 지원)",
        "서버를 두고 위키에 상시 연동해\n자동으로 최신화\n필요: 사내 서버 · 위키 접근 권한",
        "지금도 수집되고, 서버가 붙으면 자동 연동된다")


# 근거: docs/adr/0010-wiki-diff-ingest.md, backend/services/ingest.py, meta_sqlite.py
def s08_wall2():
    wall_slide(
        2, "문제 돌파 · 벽 2/4", "바뀐 건 한 줄인데, 전부 다시?",
        "조금만 바뀌어도 전체를\n다시 처리하면 느리고 비싸다",
        "내용 지문을 비교해\n바뀐 조각만 갱신하도록 구현\n변경 1~5%면 재작업 대부분 제거",
        "위키 변경에 맞춰\n정기 자동 동기화\n필요: 배치 스케줄러 운영",
        "바뀐 1~5%만 손대 재작업을 없앴다 — 실제로 구현한 방식")


# 근거: backend/services/rag.py, docs/adr/0002·0003·0004, docs/ANSWER_QUALITY.md
def s09_wall3():
    wall_slide(
        3, "문제 돌파 · 벽 3/4", "그럴듯한 답 말고, 맞는 답",
        "단순 검색은 엉뚱한 근거로\n그럴듯하게 틀린다",
        "뜻+단어 함께 찾기 · 조각 크기 조정 ·\n출처 표시를 구현\n최상위 적중률 62% → 81%",
        "전체 편람으로 평가 문항 확대 재측정 +\n확신 낮은 답은 상담원 검토\n필요: 정기 평가 체계",
        "정확도를 실제로 끌어올렸다 (다음 장 수치)")


# 근거: docs/adr/0001-llm-service-abstraction.md, backend/services/embedder.py(make_llm),
#        docs/ONPREM_ROADMAP.md
def s10_wall4():
    # 정직성: 외부는 '생성 AI 1곳'뿐, 검색·기억(임베딩)은 이미 사내 로컬임을 분명히 한다.
    wall_slide(
        4, "문제 돌파 · 벽 4/4", "지금은 외부 AI, 곧 사내 AI",
        "폐쇄망에서 바로 쓸\n사내 생성 AI가 아직 없다",
        "검색·기억은 이미 전부 사내에서 동작\n생성 AI만 갈아끼우기 쉽게 설계\n(외부는 생성 1곳만 임시)",
        "사내망 모델을 붙여\n코드 변경 없이 즉시 교체 → 완전 사내화\n필요: 사내 GPU 서버 · 사내 LLM",
        "핵심은 이미 사내에서 돈다 — 생성만 갈아끼우면 완전 사내화")


# ── 슬라이드 10.5 (신규). [개요] 시스템 구조 ───────────────────
# 근거: docs/adr/0001-llm-service-abstraction.md(LLM 추상화·모델 교체),
#        docs/adr/0002-chromadb-dual-collection.md(데이터 계층), api-spec.md(4계층 분리),
#        아키텍쳐/_render_arch.html(전체 시스템 아키텍처 도해).
# 위치: 벽 4/4(s10) 다음, 시연(s11) 앞에 삽입 → 시연 전에 "구조가 갈아끼우기 쉽다"를 각인.
#        (연관: build()에서 s10_wall4() → s10p5_architecture() → s11_demo() 순서로 호출)
def s10p5_architecture():
    s = slide()
    header(s, "개요 · 시스템 구조", "시스템 구조")
    # HTML → PNG 변환 (아키텍쳐/_render_arch.html)
    arch_html = os.path.join(_ARCH_DIR, "_render_arch.html")
    arch_png = os.path.join(_TMP_DIR, "arch.png")
    png = html_to_png(arch_html, arch_png, width=1300, height=680)
    # 이미지 삽입 영역: 약 11인치 × 5.2인치, 슬라이드 가로 중앙
    iw, ih = Inches(11.6), Inches(5.2)
    ix = Emu(int((SW - iw) / 2))
    iy = Inches(1.75)
    if png:
        pic = s.shapes.add_picture(png, ix, iy, width=iw)
        if pic.height > ih:
            pic._element.getparent().remove(pic._element)
            pic = s.shapes.add_picture(png, ix, iy, height=ih)
            pic.left = Emu(int((SW - pic.width) / 2))
        pic.top = Inches(1.75)
    else:
        placeholder(s, ix, iy, iw, ih,
                    "시스템 아키텍처 — 아키텍쳐/_render_arch.html 렌더 실패")
    takeaway(s, "모델도 바꾸고, 데이터도 바꾸고, 화면도 바꿀 수 있다")


# ── 슬라이드 11. [시연] 영상 ───────────────────────────────────
# 근거: build_hict_customer.py 126~256줄 add_movie + _set_video_autoplay 이식
def s11_demo():
    s = slide()
    header(s, "시연", "시연")
    video_path = os.environ.get(
        "HICT_VIDEO",
        os.path.join(os.path.dirname(__file__), "..", "..",
                     "demo_시연영상_실제버전.mp4"))
    video_path = os.path.abspath(video_path)
    vx, vy, vw, vh = Inches(1.9), Inches(1.9), Inches(9.5), Inches(4.35)
    placed = False
    if os.path.exists(video_path):
        try:
            # 영상 테두리 프레임
            rect(s, vx - Inches(0.06), vy - Inches(0.06),
                 vw + Inches(0.12), vh + Inches(0.12),
                 ESPRESSO, round_=False)
            mv = s.shapes.add_movie(video_path, vx, vy, vw, vh,
                                    mime_type="video/mp4")
            _set_video_autoplay(mv)
            placed = True
        except Exception as e:
            print("  [경고] 영상 임베드 실패, 자리표시로 대체:", e)
            placed = False
    if not placed:
        placeholder(s, vx, vy, vw, vh,
                    "▶  시연 영상 — 이 자리에 영상을 올리세요")
    note = ("슬라이드쇼 진입 시 자동재생됩니다."
            if placed else
            "발표 시 이 박스 위에 시연 영상(MP4)을 끌어다 놓으세요.")
    put_text(s, Inches(1.9), Inches(6.35), Inches(9.5), Inches(0.35),
             [(note, 11, False, TAUPE, PP_ALIGN.CENTER)])
    takeaway(s, "응대 → 훈련까지, 한 화면에서")


def _set_video_autoplay(movie_shape):
    """영상이 슬라이드 진입 시 자동재생되도록 timing XML 삽입.
    (출처: build_hict_customer.py 183~256줄 _set_video_autoplay 그대로 이식)"""
    pic = movie_shape._element
    nv = pic.find(qn('p:nvPicPr'))
    if nv is None:
        return
    cNvPr = nv.find(qn('p:cNvPr'))
    if cNvPr is None:
        return
    sp_id = cNvPr.get('id')
    root = pic
    while root.tag != qn('p:sld') and root.getparent() is not None:
        root = root.getparent()
    if root.tag != qn('p:sld'):
        return
    for old in root.findall(qn('p:timing')):
        root.remove(old)
    P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
    timing_xml = f'''<p:timing xmlns:p="{P}">
  <p:tnLst>
    <p:par>
      <p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">
        <p:childTnLst>
          <p:seq concurrent="1" nextAc="seek">
            <p:cTn id="2" dur="indefinite" nodeType="mainSeq">
              <p:childTnLst>
                <p:par>
                  <p:cTn id="3" fill="hold">
                    <p:stCondLst><p:cond delay="indefinite"/></p:stCondLst>
                    <p:childTnLst>
                      <p:par>
                        <p:cTn id="4" fill="hold">
                          <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                          <p:childTnLst>
                            <p:par>
                              <p:cTn id="5" presetClass="mediacall" presetID="1" fill="hold" nodeType="afterEffect">
                                <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                                <p:childTnLst>
                                  <p:cmd type="call" cmd="playFrom(0.0)">
                                    <p:cBhvr>
                                      <p:cTn id="6" dur="1" fill="hold"/>
                                      <p:tgtEl><p:spTgt spid="{sp_id}"/></p:tgtEl>
                                    </p:cBhvr>
                                  </p:cmd>
                                </p:childTnLst>
                              </p:cTn>
                            </p:par>
                          </p:childTnLst>
                        </p:cTn>
                      </p:par>
                    </p:childTnLst>
                  </p:cTn>
                </p:par>
              </p:childTnLst>
            </p:cTn>
            <p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>
            <p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>
          </p:seq>
        </p:childTnLst>
      </p:cTn>
    </p:par>
  </p:tnLst>
</p:timing>'''
    from pptx.oxml import parse_xml
    root.append(parse_xml(timing_xml))


# ── 슬라이드 12. [기대효과] 3요소 ──────────────────────────────
# 근거: 기회 프레임(금액·비용절감 문구 금지). README.md 기대효과, value-framing 원칙.
def s12_effects():
    s = slide()
    header(s, "기대효과", "기대 효과")
    items = [("응대 시간 단축", "편람 헤매던 시간을 줄인다"),
             ("답변 품질 균일화", "누가 받아도 같은 수준의 답"),
             ("신입 교육 지원", "AI 코치로 더 빨리 익힌다")]
    gap = Inches(0.4)
    total = Inches(12.1)
    n = len(items)
    w = Emu(int((total - gap * (n - 1)) / n))
    x = Inches(0.62)
    for i, (head, desc) in enumerate(items):
        c = card(s, x, Inches(2.35), w, Inches(3.0))
        shape_text(c, [
            (str(i + 1).zfill(2), 28, True, ORANGE, PP_ALIGN.LEFT, FONT_EN),
            (head, 18, True, ESPRESSO, PP_ALIGN.LEFT),
            ("", 6, False, ESPRESSO, PP_ALIGN.LEFT),
            (desc, 13.5, False, TAUPE, PP_ALIGN.LEFT),
        ], anchor=MSO_ANCHOR.TOP, ml=0.26, mt=0.24)
        x = Emu(int(x + w + gap))
    put_text(s, Inches(0.62), Inches(5.55), Inches(12.1), Inches(0.4),
             [("같은 인원으로 더 많은 · 더 고른 응대", 14, True, TAUPE, PP_ALIGN.CENTER)])
    takeaway(s, "빠르게, 고르게, 빨리 배운다")


# ── 슬라이드 13. [기대효과] 정확도 근거 (정직) ─────────────────
# 근거: docs/ANSWER_QUALITY.md, docs/api-spec.md(하이브리드), tests/test_questions.json(30문항)
def s13_numbers():
    s = slide()
    header(s, "기대효과 · 근거", "성능 지표")
    # 정직성(재조사 확정): 검색 hit@3=100%는 자체 30문항 실측, 개선효과 62→81%는 16문항 실측,
    # 답변 80%는 15문항 의미채점(12/15) 실측. '100문항' 측정은 존재하지 않음 → 재측정 예정(계획)일 뿐.
    kpis = [("100%", "근거 문서를 상위 3개 안에서\n찾는 비율 (자체 30문항)"),
            ("62% → 81%", "뜻+단어 함께 찾기로\n최상위 적중률 상승"),
            ("80%", "답변 정확도\n(15문항 채점 결과)")]
    gap = Inches(0.4)
    total = Inches(12.1)
    n = len(kpis)
    w = Emu(int((total - gap * (n - 1)) / n))
    x = Inches(0.62)
    for big, sub in kpis:
        c = card(s, x, Inches(2.15), w, Inches(3.05))
        shape_text(c, [
            (big, 40, True, ORANGED, PP_ALIGN.CENTER, FONT_EN),
            ("", 8, False, ESPRESSO, PP_ALIGN.CENTER),
        ] + [(l, 13, False, ESPRESSO, PP_ALIGN.CENTER)
             for l in sub.split("\n")],
            anchor=MSO_ANCHOR.MIDDLE, space=3)
        x = Emu(int(x + w + gap))
    put_text(s, Inches(0.62), Inches(5.4), Inches(12.1), Inches(0.6),
             [("측정 기준 — 검색: 자체 30문항(개선 효과는 16문항) · 답변: 15문항 의미 채점",
               11, False, TAUPE, PP_ALIGN.CENTER),
              ("신뢰도를 더 다지기 위해 평가 문항을 100문항으로 늘려 재측정 예정",
               11, False, TAUPE, PP_ALIGN.CENTER)])
    takeaway(s, "검색은 이미 최상위, 답변도 실측으로 확인")


# ── 슬라이드 14. [앞으로] 도입 청사진 ──────────────────────────
# 근거: docs/ONPREM_ROADMAP.md, docs/adr/0002(저장소), api-spec.md
def s14_blueprint():
    s = slide()
    header(s, "앞으로 · 도입 청사진", "도입 요건")
    # 정직성: MCP는 현재 코드 미적용 → '향후'로만 표기.
    items = [("서버", "사내 GPU 서버에 올려 폐쇄망에서 운영"),
             ("기업용 지식 저장소", "지금은 시험용, 실도입 땐 기업용으로 교체"),
             ("사내 DB 연동", "편람·시스템과 직접 연결"),
             ("표준 연동 활용", "사내 시스템을 표준 방식으로 연결 (향후)")]
    gap_x, gap_y = Inches(0.35), Inches(0.3)
    w = Inches(5.87)
    h = Inches(1.62)
    x0, y0 = Inches(0.62), Inches(2.15)
    for i, (head, desc) in enumerate(items):
        cx = Emu(int(x0 + (i % 2) * (w + gap_x)))
        cy = Emu(int(y0 + (i // 2) * (h + gap_y)))
        c = card(s, cx, cy, w, h)
        put_text(s, cx + Inches(0.28), cy, w - Inches(0.5), h,
                 [(head, 17, True, ORANGED, PP_ALIGN.LEFT),
                  (desc, 13, False, ESPRESSO, PP_ALIGN.LEFT)],
                 anchor=MSO_ANCHOR.MIDDLE, space=4)
    takeaway(s, "POC를 실서비스로 올리는 길")


# ── 슬라이드 15. [앞으로] 타 증권사 현황 (자리표시) ────────────
# 근거: 없음(자료 미확보) → 창작 절대 금지, 자리표시만.
def s15_others():
    s = slide()
    header(s, "앞으로 · 도입 근거", "업계 현황")
    placeholder(s, Inches(0.62), Inches(2.35), Inches(12.1), Inches(3.0),
                "※ 타 증권사 AI 상담 도입 현황 — 자료 반영 예정")
    takeaway(s, "업계 흐름이 도입의 근거가 된다")


# ── 슬라이드 16. [앞으로] 도입 프레이밍 ────────────────────────
# 근거: value-framing 원칙, ONPREM_ROADMAP.md
def s16_framing():
    s = slide()
    header(s, "앞으로 · 우리의 제안", "제안")
    c = card(s, Inches(0.62), Inches(2.1), Inches(12.1), Inches(1.6),
             fill=WHITE, line=ORANGE, line_w=1.75)
    shape_text(c, [("도입하려면 이런 환경과 기술이 필요합니다",
                    26, True, ESPRESSO, PP_ALIGN.CENTER)],
               anchor=MSO_ANCHOR.MIDDLE)
    three = ["사내 서버", "사내 AI 모델", "데이터 연동"]
    gap = Inches(0.35)
    total = Inches(12.1)
    w = Emu(int((total - gap * 2) / 3))
    x = Inches(0.62)
    for t in three:
        cc = card(s, x, Inches(3.95), w, Inches(1.15))
        shape_text(cc, [(t, 17, True, ORANGED, PP_ALIGN.CENTER)],
                   anchor=MSO_ANCHOR.MIDDLE)
        x = Emu(int(x + w + gap))
    put_text(s, Inches(0.62), Inches(5.35), Inches(12.1), Inches(0.5),
             [("환경만 갖춰지면 바로 올릴 수 있다", 15, True, TAUPE, PP_ALIGN.CENTER)])
    takeaway(s, "우리는 준비됐다 — 남은 건 환경")


# ── 슬라이드 17. 클로징 ────────────────────────────────────────
def s17_closing():
    s = prs.slides.add_slide(BLANK)   # 페이지번호/takeaway 없이 깔끔하게
    bg(s)
    rect(s, Inches(1.1), Inches(2.9), Inches(0.12), Inches(1.7), ORANGE, round_=False)
    put_text(s, Inches(1.45), Inches(3.0), Inches(11), Inches(1.4),
             [("물어보면 답하고, 답하면 채점하는 AI", 34, True, ESPRESSO, PP_ALIGN.LEFT)])
    put_text(s, Inches(1.45), Inches(4.55), Inches(11), Inches(0.5),
             [("한화투자증권 ITO", 16, True, TAUPE, PP_ALIGN.LEFT)])


# ── 부록 A1~A4 ─────────────────────────────────────────────────
def appendix(kicker, title, rows, note_txt=None):
    """부록 공통: kicker '부록' + 제목 + 간결한 리스트 카드 1장."""
    s = slide()
    header(s, kicker, title)
    c = card(s, Inches(0.62), Inches(2.1), Inches(12.1),
             Inches(3.9) if note_txt else Inches(4.2))
    lines = []
    for i, (head, desc) in enumerate(rows):
        lines.append((f"·  {head}", 16, True, ESPRESSO, PP_ALIGN.LEFT))
        lines.append((f"    {desc}", 13, False, TAUPE, PP_ALIGN.LEFT))
    shape_text(c, lines, anchor=MSO_ANCHOR.MIDDLE, ml=0.4, space=6)
    if note_txt:
        put_text(s, Inches(0.9), Inches(6.25), Inches(11.5), Inches(0.5),
                 [(note_txt, 11, False, TAUPE, PP_ALIGN.LEFT)])


# 근거: README.md:333-342 (성공 기준)
def a1_criteria():
    appendix("부록 · A1", "성공 기준", [
        ("답변 정확도", "80% 이상"),
        ("출처 정확도", "90% 이상"),
        ("응답 속도", "3초 이내"),
        ("환각(잘못된 답)", "5% 미만"),
    ])


# 근거: docs/ONPREM_ROADMAP.md, 위키수집_파이프라인_발표노트.md
def a2_roadmap():
    appendix("부록 · A2", "로드맵", [
        ("7월", "PoC 완성"),
        ("8월", "사내 GPU 환경 준비"),
        ("9월", "고객사 선제안"),
    ])


# 근거: docs/ONPREM_ROADMAP.md(폐쇄망 상주), README.md(보안)
def a3_compliance():
    appendix("부록 · A3", "컴플라이언스", [
        ("개인정보·금융 규제 대응", "규제 요건에 맞춘 처리"),
        ("폐쇄망 내 데이터 상주", "데이터는 사내에만 머문다"),
        ("외부 전송 없음", "생성 AI 교체 시 완전 사내화"),
    ])


# 근거: docs/ONPREM_ROADMAP.md, README.md(보안 상세)
def a4_security():
    appendix("부록 · A4", "보안 상세", [
        ("통합인증 수집", "사내 통합 인증 연동"),
        ("사내 SSL 대응", "사내 보안 통신 대응"),
        ("폐쇄망 이식", "벡터 저장소 폴더 이동만으로 이식"),
    ])


# ── 빌드 ────────────────────────────────────────────────────────
def build():
    # 시작 시 임시 PNG 폴더 확보(HTML→PNG 변환 결과 저장처). 절대경로.
    ensure_tmp()
    s01_cover()
    s02_scattered()
    s03_problem()
    s04_two_modes()
    s05_flow()          # 변경: 흐름도 HTML(_render_flow.html) 이미지 삽입
    s06_plus_alpha()
    s07_wall1()
    s08_wall2()
    s09_wall3()
    s10_wall4()
    s10p5_architecture()  # 신규: 시스템 아키텍처 HTML(_render_arch.html) 이미지 삽입
    s11_demo()
    s12_effects()
    s13_numbers()
    s14_blueprint()
    s15_others()
    s16_framing()
    s17_closing()
    # 부록
    a1_criteria()
    a2_roadmap()
    a3_compliance()
    a4_security()

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "ITO_AX_Day_상담원AI코치_temp.pptx")
    prs.save(out)
    n = len(prs.slides._sldIdLst)
    print(f"[완료] 저장: {out}")
    print(f"[확인] 총 슬라이드 수: {n} (본편 18 + 부록 4 = 22 기대)")


if __name__ == "__main__":
    build()
