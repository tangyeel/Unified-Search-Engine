"""
github_search.py - GitHub search engine for TracePath/DocuPulse.
Pure search layer. No storage. No graph. Returns ranked results.
"""

from __future__ import annotations

import os
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

import requests
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from services.http_client import build_session

SearchKind = Literal["code", "repositories", "issues", "commits", "users", "topics"]

SORT_OPTIONS: dict[SearchKind, list[str]] = {
    "code": ["indexed"],
    "repositories": ["stars", "forks", "help-wanted-issues", "updated"],
    "issues": [
        "comments",
        "reactions",
        "reactions-+1",
        "reactions--1",
        "reactions-smile",
        "reactions-tada",
        "reactions-thinking_face",
        "reactions-heart",
        "reactions-rocket",
        "reactions-eyes",
        "interactions",
        "created",
        "updated",
    ],
    "commits": ["author-date", "committer-date"],
    "users": ["followers", "repositories", "joined"],
    "topics": [],
}

GITHUB_API = "https://api.github.com"
MAX_PER_PAGE = 100


# --- Token pool -------------------------------------------------------------

@dataclass
class _Token:
    value: str
    remaining: int = 30
    reset_at: float = 0.0
    failures: int = 0

    @property
    def exhausted(self) -> bool:
        return self.remaining == 0 and time.time() < self.reset_at

    @property
    def healthy(self) -> bool:
        return self.failures < 3 and not self.exhausted


class _TokenPool:
    def __init__(self, tokens: list[str]):
        if not tokens:
            raise ValueError("Provide at least one GitHub token.")
        self._pool = [_Token(t.strip()) for t in tokens if t.strip()]
        self._lock = threading.Lock()

    def acquire(self) -> _Token:
        with self._lock:
            healthy = [t for t in self._pool if t.healthy]
            if not healthy:
                soonest = min(self._pool, key=lambda t: t.reset_at)
                wait = max(0, soonest.reset_at - time.time()) + 1
                raise RateLimitError(
                    f"All tokens exhausted. Retry in {wait:.0f}s.",
                    retry_after=wait,
                )
            return min(healthy, key=lambda t: t.failures * 1000 + (30 - t.remaining))

    def update(self, tok: _Token, headers: dict):
        with self._lock:
            tok.remaining = int(headers.get("X-RateLimit-Remaining", tok.remaining))
            reset_ts = headers.get("X-RateLimit-Reset")
            if reset_ts:
                tok.reset_at = float(reset_ts)
            tok.failures = 0

    def penalize(self, tok: _Token):
        with self._lock:
            tok.failures += 1

    @property
    def status(self) -> list[dict]:
        return [
            {
                "token_prefix": t.value[:12] + "...",
                "remaining": t.remaining,
                "reset_in": max(0, t.reset_at - time.time()),
                "healthy": t.healthy,
            }
            for t in self._pool
        ]


# --- Exceptions -------------------------------------------------------------

class GitHubSearchError(Exception):
    pass


class RateLimitError(GitHubSearchError):
    def __init__(self, msg: str, retry_after: float = 60):
        super().__init__(msg)
        self.retry_after = retry_after


class AuthError(GitHubSearchError):
    pass


class SearchSyntaxError(GitHubSearchError):
    pass


# --- Result models ----------------------------------------------------------

@dataclass
class CodeResult:
    name: str
    path: str
    repo: str
    repo_url: str
    file_url: str
    language: str
    sha: str
    score: float
    text_match: str = ""


@dataclass
class RepoResult:
    full_name: str
    description: str
    url: str
    language: str
    stars: int
    forks: int
    open_issues: int
    topics: list[str]
    license: str
    updated_at: str
    score: float


@dataclass
class IssueResult:
    number: int
    title: str
    state: str
    repo: str
    url: str
    author: str
    comments: int
    labels: list[str]
    created_at: str
    updated_at: str
    score: float


@dataclass
class CommitResult:
    sha: str
    message: str
    author: str
    author_date: str
    repo: str
    url: str
    score: float


@dataclass
class UserResult:
    login: str
    name: str
    bio: str
    company: str
    location: str
    public_repos: int
    followers: int
    url: str
    score: float


@dataclass
class SearchResponse:
    kind: SearchKind
    query: str
    total_count: int
    incomplete_results: bool
    items: list[Any]
    page: int
    per_page: int
    elapsed_ms: int
    token_status: list[dict] = field(default_factory=list)

    @property
    def has_more(self) -> bool:
        return (self.page * self.per_page) < min(self.total_count, 1000)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "query": self.query,
            "total_count": self.total_count,
            "incomplete_results": self.incomplete_results,
            "page": self.page,
            "per_page": self.per_page,
            "elapsed_ms": self.elapsed_ms,
            "has_more": self.has_more,
            "items": [vars(item) for item in self.items],
            "token_status": self.token_status,
        }


def _parse_code(raw: dict) -> CodeResult:
    repo = raw.get("repository", {})
    fragments = raw.get("text_matches", [])
    snippet = fragments[0].get("fragment", "") if fragments else ""
    return CodeResult(
        name=raw.get("name", ""),
        path=raw.get("path", ""),
        repo=repo.get("full_name", ""),
        repo_url=repo.get("html_url", ""),
        file_url=raw.get("html_url", ""),
        language=repo.get("language", "") or "",
        sha=raw.get("sha", ""),
        score=raw.get("score", 0.0),
        text_match=snippet,
    )


def _parse_repo(raw: dict) -> RepoResult:
    lic = raw.get("license") or {}
    return RepoResult(
        full_name=raw.get("full_name", ""),
        description=raw.get("description", "") or "",
        url=raw.get("html_url", ""),
        language=raw.get("language", "") or "",
        stars=raw.get("stargazers_count", 0),
        forks=raw.get("forks_count", 0),
        open_issues=raw.get("open_issues_count", 0),
        topics=raw.get("topics", []),
        license=lic.get("name", "") or "",
        updated_at=raw.get("updated_at", ""),
        score=raw.get("score", 0.0),
    )


def _parse_issue(raw: dict) -> IssueResult:
    repo_url = raw.get("repository_url", "")
    repo = "/".join(repo_url.split("/")[-2:]) if repo_url else ""
    return IssueResult(
        number=raw.get("number", 0),
        title=raw.get("title", ""),
        state=raw.get("state", ""),
        repo=repo,
        url=raw.get("html_url", ""),
        author=(raw.get("user") or {}).get("login", ""),
        comments=raw.get("comments", 0),
        labels=[lb.get("name", "") for lb in raw.get("labels", [])],
        created_at=raw.get("created_at", ""),
        updated_at=raw.get("updated_at", ""),
        score=raw.get("score", 0.0),
    )


def _parse_commit(raw: dict) -> CommitResult:
    commit = raw.get("commit", {})
    author = commit.get("author", {})
    repo = raw.get("repository", {})
    return CommitResult(
        sha=raw.get("sha", "")[:12],
        message=(commit.get("message", "") or "").split("\n")[0][:120],
        author=author.get("name", "") or (raw.get("author") or {}).get("login", ""),
        author_date=author.get("date", ""),
        repo=repo.get("full_name", ""),
        url=raw.get("html_url", ""),
        score=raw.get("score", 0.0),
    )


def _parse_user(raw: dict) -> UserResult:
    return UserResult(
        login=raw.get("login", ""),
        name=raw.get("name", "") or "",
        bio=raw.get("bio", "") or "",
        company=raw.get("company", "") or "",
        location=raw.get("location", "") or "",
        public_repos=raw.get("public_repos", 0),
        followers=raw.get("followers", 0),
        url=raw.get("html_url", ""),
        score=raw.get("score", 0.0),
    )


_PARSERS = {
    "code": _parse_code,
    "repositories": _parse_repo,
    "issues": _parse_issue,
    "commits": _parse_commit,
    "users": _parse_user,
    "topics": lambda r: r,
}


class GitHubSearchEngine:
    def __init__(self, tokens: list[str], timeout: int = 10, retries: int = 2):
        self._pool = _TokenPool(tokens)
        self._timeout = timeout
        self._retries = retries
        self._session = build_session()
        self._session.headers.update(
            {
                "Accept": "application/vnd.github+json,application/vnd.github.text-match+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def search(
        self,
        q: str,
        kind: SearchKind = "code",
        *,
        sort: Optional[str] = None,
        order: Literal["asc", "desc"] = "desc",
        limit: int = 30,
        page: int = 1,
    ) -> SearchResponse:
        if not q.strip():
            raise SearchSyntaxError("Query cannot be empty.")

        limit = max(1, min(limit, MAX_PER_PAGE))
        params: dict[str, Any] = {"q": q, "per_page": limit, "page": page}
        if sort and sort in SORT_OPTIONS.get(kind, []):
            params["sort"] = sort
            params["order"] = order

        url = f"{GITHUB_API}/search/{kind}"
        t0 = time.monotonic()
        data = self._request(url, params)
        elapsed = int((time.monotonic() - t0) * 1000)

        parser = _PARSERS[kind]
        items = [parser(item) for item in data.get("items", [])]

        return SearchResponse(
            kind=kind,
            query=q,
            total_count=data.get("total_count", 0),
            incomplete_results=data.get("incomplete_results", False),
            items=items,
            page=page,
            per_page=limit,
            elapsed_ms=elapsed,
            token_status=self._pool.status,
        )

    def _request(self, url: str, params: dict) -> dict:
        last_error = None
        for attempt in range(self._retries + 1):
            tok = self._pool.acquire()
            self._session.headers["Authorization"] = f"Bearer {tok.value}"
            try:
                resp = self._session.get(url, params=params, timeout=self._timeout)
                self._pool.update(tok, resp.headers)

                if resp.status_code == 200:
                    return resp.json()

                if resp.status_code == 401:
                    self._pool.penalize(tok)
                    raise AuthError("Token rejected by GitHub (401). Check scopes.")

                if resp.status_code == 403:
                    body = resp.json()
                    msg = body.get("message", "")
                    if "rate limit" in msg.lower():
                        self._pool.penalize(tok)
                        retry_after = float(resp.headers.get("Retry-After", 60))
                        raise RateLimitError(msg, retry_after=retry_after)
                    raise GitHubSearchError(f"GitHub 403: {msg}")

                if resp.status_code == 422:
                    body = resp.json()
                    raise SearchSyntaxError(f"Invalid query: {body.get('message', '')}")

                if resp.status_code == 503:
                    last_error = GitHubSearchError("GitHub search unavailable (503). Retrying...")
                    time.sleep(2 ** attempt)
                    continue

                body = resp.json()
                raise GitHubSearchError(
                    f"GitHub {resp.status_code}: {body.get('message', 'Unknown error')}"
                )

            except (AuthError, SearchSyntaxError, RateLimitError):
                raise
            except requests.RequestException as e:
                last_error = GitHubSearchError(f"Network error: {e}")
                self._pool.penalize(tok)
                time.sleep(1.5 ** attempt)
                continue

        raise last_error or GitHubSearchError("Request failed after retries.")

    @property
    def token_status(self) -> list[dict]:
        return self._pool.status


# --- FastAPI integration ----------------------------------------------------

router = APIRouter(prefix="/search/github", tags=["Search"])
_engine: Optional[GitHubSearchEngine] = None


class TokenConfig(BaseModel):
    tokens: list[str]


def _get_env_tokens() -> list[str]:
    tokens = os.getenv("GITHUB_TOKENS") or ""
    if tokens.strip():
        return [t.strip() for t in tokens.split(",") if t.strip()]
    single = os.getenv("GITHUB_TOKEN")
    return [single] if single else []


@router.post("/configure")
def configure_tokens(cfg: TokenConfig):
    global _engine
    _engine = GitHubSearchEngine(cfg.tokens)
    return {"status": "ok", "token_count": len(cfg.tokens)}


@router.get("")
def github_search(
    q: str = Query(..., description="GitHub search query"),
    kind: SearchKind = Query("code"),
    sort: Optional[str] = Query(None),
    order: Literal["asc", "desc"] = Query("desc"),
    limit: int = Query(20, ge=1, le=100),
    page: int = Query(1, ge=1),
    x_github_token: str | None = Header(default=None, alias="X-GitHub-Token"),
):
    engine = _engine
    if x_github_token:
        engine = GitHubSearchEngine([x_github_token])
    if engine is None:
        env_tokens = _get_env_tokens()
        if env_tokens:
            engine = GitHubSearchEngine(env_tokens)
    if engine is None:
        raise HTTPException(422, "No tokens configured. POST /search/github/configure first.")
    try:
        return engine.search(q, kind, sort=sort, order=order, limit=limit, page=page).to_dict()
    except RateLimitError as e:
        raise HTTPException(429, str(e))
    except AuthError as e:
        raise HTTPException(401, str(e))
    except SearchSyntaxError as e:
        raise HTTPException(400, str(e))
    except GitHubSearchError as e:
        raise HTTPException(502, str(e))


@router.get("/token-status")
def token_status():
    if _engine is None:
        raise HTTPException(422, "No tokens configured.")
    return _engine.token_status
