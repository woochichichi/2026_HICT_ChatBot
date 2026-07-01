"""오답 제보(피드백) 저장소 — 로컬 SQLite (api-spec.md 섹션 11).

응대 모드에서 상담사가 "이 답변 틀렸다"고 제보한 내용을 누적 저장하고,
운영자가 검토 화면에서 조회/처리(resolve)하는 데 사용.

설계: stores/meta_sqlite.py 의 MetaStore 패턴을 미러(WAL, row_factory, executescript).
폐쇄망 대비 외부 의존 0 — data/feedback.db 파일 1개.

이 모듈을 사용하는 곳:
  - backend/routers/feedback.py: POST/GET /api/feedback, resolve

⚠️ 동시성: 요청마다 인스턴스를 새로 만들고 `with`로 닫음(모듈 전역 단일
connection 공유 금지 — sqlite3는 check_same_thread 기본 True라 스레드풀에서 깨짐).
connect(timeout=5.0)로 짧은 write lock 경합 흡수. resolve는 status='open' 조건부
UPDATE + rowcount로 이중 처리(레이스) 방지(dev-harness 선점 상태변경 패턴).
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT NOT NULL,        -- UTC ISO (시간대 이중변환 방지)
    question      TEXT NOT NULL,        -- 제보 대상 유저 질문 스냅샷
    answer        TEXT NOT NULL,        -- AI 답변 본문 스냅샷
    reason        TEXT NOT NULL,        -- 제보 사유 (필수)
    suggested     TEXT,                 -- 정답 제안 (선택)
    sources_json  TEXT,                 -- sources[] JSON 직렬화 스냅샷
    confidence    TEXT,                 -- high|medium|low 스냅샷
    status        TEXT DEFAULT 'open',  -- open | resolved
    resolved_at   TEXT,
    resolver_note TEXT
);
CREATE INDEX IF NOT EXISTS idx_feedback_status ON feedback(status);
"""


def _now() -> str:
    """UTC ISO 문자열 — 저장은 UTC 고정(시간대 이중 변환 방지)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class FeedbackStore:
    """오답 제보 저장소. with 문 또는 close()로 정리."""

    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        # timeout=5.0: 검토 resolve 와 submit 동시 발생 시 짧은 write lock 경합 흡수
        self.conn = sqlite3.connect(db_path, timeout=5.0)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    # --- 쓰기 ---

    def submit(
        self,
        *,
        question: str,
        answer: str,
        reason: str,
        suggested: str | None,
        sources_json: str | None,
        confidence: str | None,
    ) -> int:
        """제보 1건 등록. 반환: 생성된 id."""
        cur = self.conn.execute(
            """
            INSERT INTO feedback
                (created_at, question, answer, reason, suggested,
                 sources_json, confidence, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'open')
            """,
            (_now(), question, answer, reason, suggested, sources_json, confidence),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def resolve(self, feedback_id: int, note: str | None = None) -> bool:
        """제보를 처리완료(resolved)로 전환.

        status='open' 조건부 UPDATE → rowcount>0 이면 이번 호출이 선점 성공.
        이미 resolved 거나 없는 id면 False(라우터에서 404).
        """
        cur = self.conn.execute(
            "UPDATE feedback SET status='resolved', resolved_at=?, resolver_note=? "
            "WHERE id=? AND status='open'",
            (_now(), note, feedback_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    # --- 읽기 ---

    def list(self, status: str | None = None) -> list[sqlite3.Row]:
        """제보 목록(id 내림차순). status 지정 시 해당 상태만."""
        if status:
            return self.conn.execute(
                "SELECT * FROM feedback WHERE status=? ORDER BY id DESC",
                (status,),
            ).fetchall()
        return self.conn.execute(
            "SELECT * FROM feedback ORDER BY id DESC"
        ).fetchall()

    # --- lifecycle ---

    def close(self) -> None:
        # 제보는 소량 → MetaStore 와 달리 WAL checkpoint(TRUNCATE) 생략
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
