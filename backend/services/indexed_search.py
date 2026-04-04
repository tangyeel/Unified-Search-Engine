from __future__ import annotations

import json
import os
import hashlib
import sqlite3
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query

from services.github_search import GitHubSearchEngine, AuthError as GhAuthError, GitHubSearchError
from services.slack_search import SlackSearchEngine, AuthError as SlackAuthError, SlackSearchError
from services.gdrive_search import GDriveSearchEngine, AuthError as GdAuthError, GDriveSearchError


router = APIRouter(tags=["Indexed Search"])

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "search_index.db")


def _ensure_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS docs (
                id TEXT PRIMARY KEY,
                source TEXT,
                kind TEXT,
                title TEXT,
                snippet TEXT,
                url TEXT,
                meta TEXT,
                score REAL,
                indexed_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts
            USING fts5(title, snippet, content='docs', content_rowid='rowid')
            """
        )
        conn.commit()


def _doc_id(source: str, kind: str, url: str, title: str) -> str:
    raw = f"{source}|{kind}|{url}|{title}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _split_tokens(raw: str) -> list[str]:
    return [t.strip() for t in raw.split(",") if t.strip()]


def _github_engine(x_token: Optional[str]) -> Optional[GitHubSearchEngine]:
    if x_token:
        return GitHubSearchEngine([x_token])
    env = os.getenv("GITHUB_TOKENS") or ""
    if env.strip():
        return GitHubSearchEngine(_split_tokens(env))
    single = os.getenv("GITHUB_TOKEN")
    return GitHubSearchEngine([single]) if single else None


def _slack_engine(x_token: Optional[str]) -> Optional[SlackSearchEngine]:
    if x_token:
        return SlackSearchEngine([x_token])
    env = os.getenv("SLACK_TOKENS") or ""
    if env.strip():
        return SlackSearchEngine(_split_tokens(env))
    single = os.getenv("SLACK_TOKEN")
    return SlackSearchEngine([single]) if single else None


def _gdrive_engine(x_token: Optional[str]) -> Optional[GDriveSearchEngine]:
    if x_token:
        return GDriveSearchEngine([x_token])
    env = os.getenv("GDRIVE_TOKENS") or ""
    if env.strip():
        return GDriveSearchEngine(_split_tokens(env))
    single = os.getenv("GDRIVE_TOKEN")
    return GDriveSearchEngine([single]) if single else None


def _normalize(source: str, kind: str, item: dict) -> dict:
    if source == "github":
        if kind == "code":
            return {
                "title": item.get("path") or item.get("name"),
                "snippet": item.get("text_match") or "",
                "url": item.get("file_url") or item.get("repo_url"),
                "meta": {"repo": item.get("repo"), "language": item.get("language")},
                "score": item.get("score", 0.0),
            }
        if kind == "repositories":
            return {
                "title": item.get("full_name"),
                "snippet": item.get("description") or "",
                "url": item.get("url"),
                "meta": {"stars": item.get("stars"), "language": item.get("language")},
                "score": item.get("score", 0.0),
            }
        if kind == "issues":
            return {
                "title": item.get("title"),
                "snippet": item.get("state"),
                "url": item.get("url"),
                "meta": {"repo": item.get("repo"), "comments": item.get("comments")},
                "score": item.get("score", 0.0),
            }
    if source == "slack":
        if kind == "messages":
            return {
                "title": f"{item.get('channel_name','dm')} · {item.get('username','')}",
                "snippet": item.get("text", ""),
                "url": item.get("permalink"),
                "meta": {"team": item.get("team"), "ts": item.get("timestamp")},
                "score": item.get("score", 0.0),
            }
        if kind == "files":
            return {
                "title": item.get("title") or item.get("name"),
                "snippet": item.get("preview", ""),
                "url": item.get("permalink"),
                "meta": {"filetype": item.get("filetype"), "size": item.get("size")},
                "score": item.get("score", 0.0),
            }
    if source == "gdrive":
        return {
            "title": item.get("name"),
            "snippet": item.get("full_text_snippet") or item.get("description", ""),
            "url": item.get("web_view_link"),
            "meta": {"mime": item.get("mime_type"), "owners": item.get("owners")},
            "score": 0.0,
        }
    return {"title": "", "snippet": "", "url": "", "meta": {}, "score": 0.0}


def _index_docs(items: list[dict]):
    if not items:
        return 0
    _ensure_db()
    now = datetime.utcnow().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        for doc in items:
            doc_id = _doc_id(doc["source"], doc["kind"], doc.get("url", ""), doc.get("title", ""))
            conn.execute(
                """
                INSERT OR REPLACE INTO docs (id, source, kind, title, snippet, url, meta, score, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
                    doc["source"],
                    doc["kind"],
                    doc.get("title", ""),
                    doc.get("snippet", ""),
                    doc.get("url", ""),
                    json.dumps(doc.get("meta", {})),
                    float(doc.get("score", 0.0)),
                    now,
                ),
            )
            rowid = conn.execute("SELECT rowid FROM docs WHERE id = ?", (doc_id,)).fetchone()[0]
            conn.execute("DELETE FROM docs_fts WHERE rowid = ?", (rowid,))
            conn.execute(
                "INSERT INTO docs_fts(rowid, title, snippet) VALUES (?, ?, ?)",
                (rowid, doc.get("title", ""), doc.get("snippet", "")),
            )
        conn.commit()
    return len(items)


@router.post("/search/index/ingest")
def index_ingest(
    q: str = Query(...),
    sources: str = Query("github,slack,gdrive"),
    per_source: int = Query(10, ge=1, le=50),
    github_kind: str = Query("code"),
    slack_kind: str = Query("messages"),
    gdrive_kind: str = Query("files"),
    x_github_token: str | None = Header(default=None, alias="X-GitHub-Token"),
    x_slack_token: str | None = Header(default=None, alias="X-Slack-Token"),
    x_gdrive_token: str | None = Header(default=None, alias="X-GDrive-Token"),
):
    selected = {s.strip() for s in sources.split(",") if s.strip()}
    errors: list[dict] = []
    docs: list[dict] = []

    if "github" in selected:
        engine = _github_engine(x_github_token)
        if not engine:
            errors.append({"source": "github", "error": "Missing GitHub token"})
        else:
            try:
                resp = engine.search(q, kind=github_kind, limit=per_source).to_dict()
                for item in resp.get("items", []):
                    docs.append({"source": "github", "kind": github_kind, **_normalize("github", github_kind, item)})
            except (GhAuthError, GitHubSearchError) as e:
                errors.append({"source": "github", "error": str(e)})

    if "slack" in selected:
        engine = _slack_engine(x_slack_token)
        if not engine:
            errors.append({"source": "slack", "error": "Missing Slack token"})
        else:
            try:
                resp = engine.search(q, kind=slack_kind, limit=per_source).to_dict()
                for item in resp.get("items", []):
                    docs.append({"source": "slack", "kind": slack_kind, **_normalize("slack", slack_kind, item)})
            except (SlackAuthError, SlackSearchError) as e:
                errors.append({"source": "slack", "error": str(e)})

    if "gdrive" in selected:
        engine = _gdrive_engine(x_gdrive_token)
        if not engine:
            errors.append({"source": "gdrive", "error": "Missing Google Drive token"})
        else:
            try:
                resp = engine.search(q, kind=gdrive_kind, limit=per_source).to_dict()
                for item in resp.get("items", []):
                    docs.append({"source": "gdrive", "kind": gdrive_kind, **_normalize("gdrive", gdrive_kind, item)})
            except (GdAuthError, GDriveSearchError) as e:
                errors.append({"source": "gdrive", "error": str(e)})

    indexed = _index_docs(docs)
    return {"query": q, "indexed": indexed, "errors": errors}


@router.get("/search/index")
def index_search(
    q: str = Query(..., description="FTS query"),
    limit: int = Query(20, ge=1, le=100),
    source: Optional[str] = Query(None),
):
    _ensure_db()
    sql = """
        SELECT d.id, d.source, d.kind, d.title, d.snippet, d.url, d.meta, d.score, d.indexed_at,
               bm25(docs_fts) AS rank
        FROM docs_fts
        JOIN docs d ON docs_fts.rowid = d.rowid
        WHERE docs_fts MATCH ?
    """
    params: list = [q]
    if source:
        sql += " AND d.source = ?"
        params.append(source)
    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(sql, params).fetchall()

    results = [
        {
            "id": r[0],
            "source": r[1],
            "kind": r[2],
            "title": r[3],
            "snippet": r[4],
            "url": r[5],
            "meta": json.loads(r[6] or "{}"),
            "score": r[7],
            "indexed_at": r[8],
            "rank": r[9],
        }
        for r in rows
    ]
    return {"query": q, "count": len(results), "results": results}


@router.get("/search/index/status")
def index_status():
    _ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        count = conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
    return {"count": count, "path": DB_PATH}
