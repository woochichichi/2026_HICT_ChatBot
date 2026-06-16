"""query_expand.expand_query 단위 테스트 (api-spec.md 섹션 3).

검증 포인트:
  - 데모 버그 케이스("미국 주식")가 "해외주식"으로 보강되는지
  - 트리거 없는 질문은 원문 그대로(부작용 없음)
  - 이미 동의어가 있으면 중복 추가 안 함
"""

from backend.services.query_expand import expand_query


def test_미국주식_질문은_해외주식으로_보강된다():
    q = "미국 주식 하려면 어떻게 해야해?"
    out = expand_query(q)
    assert out.startswith(q)          # 원문 보존(추가만)
    assert "해외주식" in out          # 정답 문서 매칭용 상위어 보강


def test_트리거_없으면_원문_그대로():
    q = "비대면 계좌 잔고 조회 방법"
    assert expand_query(q) == q


def test_이미_해외주식이면_중복_추가_안함():
    q = "해외주식 매매 방법"
    # "해외 주식" 트리거는 없고, "해외주식"은 이미 있으므로 추가 없음
    assert expand_query(q) == q


def test_빈_문자열_안전():
    assert expand_query("") == ""
