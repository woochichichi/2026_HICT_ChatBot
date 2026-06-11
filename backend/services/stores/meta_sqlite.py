"""동기화 메타 DB (SQLite) — 문서 hash·청크 ID·배치 이력 (api-spec.md 섹션 9).

ChromaDB(벡터)와 분리된 "무엇이 언제 들어갔나" 추적용 저장소.
README 디렉토리 구조에 계획만 있던 stores/meta_sqlite.py의 실제 구현.

테이블:
  documents — 문서 단위 1차 스킵(raw_hash) + 삭제 감지(last_seen_at)
  chunks    — 청크 ID 집합 (ID 자체가 내용 hash라 별도 hash 컬럼 불필요)
  sync_runs — 배치 리포트 ("문서 N건 중 M건 변경 | 청크 +a/-b | 임베딩 c회")

이 모듈을 사용하는 곳:
  - backend/services/ingest.py: sync_document의 diff 비교
  - scripts/sync_manual.py: 배치 CLI
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    source_id      TEXT PRIMARY KEY,   -- 커넥터가 부여 (위키 pageId, 파일 상대경로 등)
    doc_id         TEXT NOT NULL,      -- ParsedDocument.doc_id (sha1 16자리)
    title          TEXT,
    url            TEXT,
    raw_hash       TEXT,               -- 원본 HTML sha256 — 1차 스킵 판단
    last_seen_at   TEXT,               -- 이번 동기화에서 목격된 시각 — 삭제 감지
    last_synced_at TEXT,               -- 마지막으로 ChromaDB에 반영된 시각
    status         TEXT DEFAULT 'active'  -- active | deleted
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_doc_id ON documents(doc_id);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id   TEXT PRIMARY KEY,
    doc_id     TEXT NOT NULL,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);

CREATE TABLE IF NOT EXISTS sync_runs (
    run_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at     TEXT,
    finished_at    TEXT,
    mode           TEXT,               -- full | incremental
    source         TEXT,               -- dir | crawl
    docs_total     INTEGER DEFAULT 0,
    docs_changed   INTEGER DEFAULT 0,
    docs_deleted   INTEGER DEFAULT 0,
    chunks_added   INTEGER DEFAULT 0,
    chunks_deleted INTEGER DEFAULT 0,
    embed_calls    INTEGER DEFAULT 0
);
"""


def _now() -> str:
    """UTC ISO 문자열 — 시간대 이중 변환 방지 위해 저장은 UTC 고정."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class MetaStore:
    """동기화 메타 저장소. with 문 또는 close() 호출로 정리."""

    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    # --- documents ---

    def get_document(self, source_id: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM documents WHERE source_id = ?", (source_id,)
        ).fetchone()

    def upsert_document(
        self,
        source_id: str,
        doc_id: str,
        title: str | None,
        url: str | None,
        raw_hash: str,
    ) -> None:
        """문서 동기화 성공 후 호출 — last_synced_at 갱신 포함."""
        now = _now()
        self.conn.execute(
            """
            INSERT INTO documents
                (source_id, doc_id, title, url, raw_hash,
                 last_seen_at, last_synced_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
            ON CONFLICT(source_id) DO UPDATE SET
                doc_id = excluded.doc_id,
                title = excluded.title,
                url = excluded.url,
                raw_hash = excluded.raw_hash,
                last_seen_at = excluded.last_seen_at,
                last_synced_at = excluded.last_synced_at,
                status = 'active'
            """,
            (source_id, doc_id, title, url, raw_hash, now, now),
        )
        self.conn.commit()

    def touch_seen(self, source_id: str) -> None:
        """내용 변화 없이 목격만 된 문서 — 삭제 감지용 last_seen_at만 갱신."""
        self.conn.execute(
            "UPDATE documents SET last_seen_at = ?, status = 'active' "
            "WHERE source_id = ?",
            (_now(), source_id),
        )
        self.conn.commit()

    def active_documents(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM documents WHERE status = 'active'"
        ).fetchall()

    def mark_deleted(self, source_id: str) -> None:
        # 행을 지우지 않고 status만 변경 — 복구·감사 추적 가능하게
        self.conn.execute(
            "UPDATE documents SET status = 'deleted' WHERE source_id = ?",
            (source_id,),
        )
        self.conn.commit()

    # --- chunks ---

    def get_chunk_ids(self, doc_id: str) -> set[str]:
        rows = self.conn.execute(
            "SELECT chunk_id FROM chunks WHERE doc_id = ?", (doc_id,)
        ).fetchall()
        return {r["chunk_id"] for r in rows}

    def replace_chunks(self, doc_id: str, chunk_ids: list[str]) -> None:
        """문서의 청크 ID 목록을 통째로 교체 (단일 트랜잭션 — 부분 실패 방지)."""
        now = _now()
        with self.conn:
            self.conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
            self.conn.executemany(
                "INSERT INTO chunks (chunk_id, doc_id, created_at) VALUES (?, ?, ?)",
                [(cid, doc_id, now) for cid in chunk_ids],
            )

    # --- sync_runs ---

    def record_sync_run(
        self,
        *,
        started_at: str,
        mode: str,
        source: str,
        docs_total: int,
        docs_changed: int,
        docs_deleted: int,
        chunks_added: int,
        chunks_deleted: int,
        embed_calls: int,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO sync_runs
                (started_at, finished_at, mode, source, docs_total, docs_changed,
                 docs_deleted, chunks_added, chunks_deleted, embed_calls)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (started_at, _now(), mode, source, docs_total, docs_changed,
             docs_deleted, chunks_added, chunks_deleted, embed_calls),
        )
        self.conn.commit()

    # --- lifecycle ---

    def close(self) -> None:
        # 대량 작업 후 WAL 팽창 방지 (dev-harness 규칙)
        try:
            self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error:
            pass
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def now_iso() -> str:
    """sync_manual.py에서 run 시작 시각 기록용."""
    return _now()
