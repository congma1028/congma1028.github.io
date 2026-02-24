import datetime as dt
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List

from ..models import Paper


DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "paper_agent.db"


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS papers (
              paper_id TEXT PRIMARY KEY,
              doi TEXT,
              source TEXT NOT NULL,
              title TEXT NOT NULL,
              journal TEXT,
              status TEXT NOT NULL DEFAULT 'fetched',
              first_seen_at TEXT NOT NULL,
              last_seen_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_eval_cache (
              paper_id TEXT NOT NULL,
              interests_hash TEXT NOT NULL,
              eval_json TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              PRIMARY KEY (paper_id, interests_hash)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_papers_status ON papers(status)"
        )
        conn.commit()


def upsert_papers(papers: List[Paper], db_path: Path = DEFAULT_DB_PATH) -> None:
    if not papers:
        return
    now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    with _connect(db_path) as conn:
        for p in papers:
            conn.execute(
                """
                INSERT INTO papers (paper_id, doi, source, title, journal, status, first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, 'fetched', ?, ?)
                ON CONFLICT(paper_id) DO UPDATE SET
                  doi=excluded.doi,
                  source=excluded.source,
                  title=excluded.title,
                  journal=excluded.journal,
                  last_seen_at=excluded.last_seen_at
                """,
                (p.paper_id, p.doi, p.source, p.title, p.journal, now, now),
            )
        conn.commit()


def get_paper_status_map(
    paper_ids: Iterable[str], db_path: Path = DEFAULT_DB_PATH
) -> Dict[str, str]:
    ids = [x for x in paper_ids if x]
    if not ids:
        return {}
    qmarks = ",".join(["?"] * len(ids))
    with _connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT paper_id, status FROM papers WHERE paper_id IN ({qmarks})", ids
        ).fetchall()
    return {str(r["paper_id"]): str(r["status"]) for r in rows}


def set_paper_status(
    paper_ids: Iterable[str], status: str, db_path: Path = DEFAULT_DB_PATH
) -> None:
    ids = [x for x in paper_ids if x]
    if not ids:
        return
    now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    with _connect(db_path) as conn:
        conn.executemany(
            "UPDATE papers SET status=?, last_seen_at=? WHERE paper_id=?",
            [(status, now, pid) for pid in ids],
        )
        conn.commit()


def get_eval_cache(
    interests_hash: str, db_path: Path = DEFAULT_DB_PATH
) -> Dict[str, Dict[str, Any]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT paper_id, eval_json, updated_at
            FROM llm_eval_cache
            WHERE interests_hash = ?
            """,
            (interests_hash,),
        ).fetchall()
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        paper_id = str(r["paper_id"])
        eval_data = json.loads(str(r["eval_json"]))
        out[paper_id] = {
            "paper_id": paper_id,
            "interests_hash": interests_hash,
            "updated_at": str(r["updated_at"]),
            "eval": eval_data,
        }
    return out


def upsert_eval_cache_entries(
    entries: Dict[str, Dict[str, Any]], interests_hash: str, db_path: Path = DEFAULT_DB_PATH
) -> None:
    if not entries:
        return
    now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    with _connect(db_path) as conn:
        for paper_id, payload in entries.items():
            eval_data = payload.get("eval", {})
            conn.execute(
                """
                INSERT INTO llm_eval_cache (paper_id, interests_hash, eval_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(paper_id, interests_hash) DO UPDATE SET
                  eval_json=excluded.eval_json,
                  updated_at=excluded.updated_at
                """,
                (paper_id, interests_hash, json.dumps(eval_data, ensure_ascii=False), now),
            )
        conn.commit()
