"""
slack_search.py — TracePath Slack Search Engine
Pure search layer. No storage. No graph. Just fast, ranked results.

Supports: messages · files · channels · users
Token rotation built-in — pass multiple tokens to scale across workspaces.

Slack token types:
  xoxb-...   Bot token      (search.messages requires user token)
  xoxp-...   User token     (full search access — recommended)
  xoxe-...   App-level token

Usage:
    engine = SlackSearchEngine(tokens=["xoxp-aaa", "xoxp-bbb"])
    results = engine.search("payment timeout", kind="messages", limit=20)
"""

import requests
import time
import threading
from typing import Optional, Literal, Any
from dataclasses import dataclass, field

# ── Types ─────────────────────────────────────────────────────────────────────

SearchKind = Literal["messages", "files", "all", "channels", "users"]

SORT_OPTIONS: dict[str, list[str]] = {
    "messages": ["score", "timestamp"],
    "files":    ["score", "timestamp"],
    "all":      ["score", "timestamp"],
    "channels": [],
    "users":    [],
}

SLACK_API = "https://slack.com/api"


# ── Token pool ────────────────────────────────────────────────────────────────

@dataclass
class _Token:
    value: str
    workspace: str = ""          # resolved on first use
    failures: int = 0
    tier: int = 3                # Slack tier (1=slow, 3=fast)
    calls_this_minute: int = 0
    minute_start: float = field(default_factory=time.time)

    TIER_LIMITS = {1: 1, 2: 20, 3: 50, 4: 100}

    @property
    def healthy(self) -> bool:
        return self.failures < 3

    def reset_minute_if_needed(self):
        if time.time() - self.minute_start > 60:
            self.calls_this_minute = 0
            self.minute_start = time.time()

    @property
    def rate_ok(self) -> bool:
        self.reset_minute_if_needed()
        return self.calls_this_minute < self.TIER_LIMITS.get(self.tier, 50)

    def record_call(self):
        self.reset_minute_if_needed()
        self.calls_this_minute += 1


class _TokenPool:
    """Round-robin Slack token pool with per-tier rate awareness."""

    def __init__(self, tokens: list[str]):
        if not tokens:
            raise ValueError("Provide at least one Slack token.")
        self._pool = [_Token(t.strip()) for t in tokens if t.strip()]
        self._lock = threading.Lock()

    def acquire(self) -> _Token:
        with self._lock:
            healthy = [t for t in self._pool if t.healthy and t.rate_ok]
            if not healthy:
                # Find soonest available
                soonest_wait = min(
                    60 - (time.time() - t.minute_start)
                    for t in self._pool if t.healthy
                )
                raise RateLimitError(
                    f"All tokens rate-limited. Retry in {max(0,soonest_wait):.0f}s.",
                    retry_after=max(0, soonest_wait) + 1,
                )
            return min(healthy, key=lambda t: t.calls_this_minute)

    def penalize(self, tok: _Token):
        with self._lock:
            tok.failures += 1

    def record(self, tok: _Token):
        with self._lock:
            tok.record_call()
            tok.failures = 0

    @property
    def status(self) -> list[dict]:
        return [
            {
                "token_prefix": t.value[:14] + "…",
                "workspace": t.workspace or "unknown",
                "calls_this_minute": t.calls_this_minute,
                "healthy": t.healthy,
                "rate_ok": t.rate_ok,
            }
            for t in self._pool
        ]


# ── Exceptions ────────────────────────────────────────────────────────────────

class SlackSearchError(Exception):
    pass

class RateLimitError(SlackSearchError):
    def __init__(self, msg: str, retry_after: float = 60):
        super().__init__(msg)
        self.retry_after = retry_after

class AuthError(SlackSearchError):
    pass

class SearchSyntaxError(SlackSearchError):
    pass

class ScopeError(SlackSearchError):
    """Token lacks required OAuth scope."""
    pass


# ── Result dataclasses ────────────────────────────────────────────────────────

@dataclass
class MessageResult:
    text: str                    # message body (may be truncated by Slack)
    username: str                # display name of sender
    user_id: str
    channel_id: str
    channel_name: str
    channel_type: str            # channel | group | im | mpim
    timestamp: str               # Slack ts (e.g. "1711234567.123456")
    permalink: str
    team: str
    score: float
    has_attachments: bool = False
    reactions: list[str] = field(default_factory=list)

@dataclass
class FileResult:
    id: str
    name: str
    title: str
    filetype: str
    mimetype: str
    size: int                    # bytes
    url_private: str
    permalink: str
    created: int                 # unix timestamp
    user_id: str
    username: str
    channels: list[str]          # channel names where shared
    score: float
    preview: str = ""            # text preview (if available)

@dataclass
class ChannelResult:
    id: str
    name: str
    topic: str
    purpose: str
    member_count: int
    is_private: bool
    is_archived: bool
    created: int
    creator: str

@dataclass
class UserResult:
    id: str
    name: str
    real_name: str
    display_name: str
    email: str
    title: str
    phone: str
    team_id: str
    is_admin: bool
    is_bot: bool
    tz: str
    status_text: str
    avatar_url: str

@dataclass
class SearchResponse:
    kind: SearchKind
    query: str
    total_count: int
    items: list[Any]
    page: int
    per_page: int
    page_count: int
    elapsed_ms: int
    token_status: list[dict] = field(default_factory=list)

    @property
    def has_more(self) -> bool:
        return self.page < self.page_count

    def to_dict(self) -> dict:
        def _serialize(obj):
            if hasattr(obj, "__dataclass_fields__"):
                return vars(obj)
            return obj

        return {
            "kind": self.kind,
            "query": self.query,
            "total_count": self.total_count,
            "page": self.page,
            "per_page": self.per_page,
            "page_count": self.page_count,
            "has_more": self.has_more,
            "elapsed_ms": self.elapsed_ms,
            "items": [_serialize(i) for i in self.items],
            "token_status": self.token_status,
        }


# ── Parsers ───────────────────────────────────────────────────────────────────

def _parse_message(raw: dict) -> MessageResult:
    channel = raw.get("channel", {})
    return MessageResult(
        text=raw.get("text", ""),
        username=raw.get("username", "") or raw.get("user", ""),
        user_id=raw.get("user", ""),
        channel_id=channel.get("id", ""),
        channel_name=channel.get("name", ""),
        channel_type=channel.get("is_private", False) and "private" or "public",
        timestamp=raw.get("ts", ""),
        permalink=raw.get("permalink", ""),
        team=raw.get("team", ""),
        score=raw.get("score", 0.0),
        has_attachments=bool(raw.get("attachments") or raw.get("files")),
        reactions=[r.get("name", "") for r in raw.get("reactions", [])],
    )

def _parse_file(raw: dict) -> FileResult:
    shares = raw.get("shares", {})
    channel_names: list[str] = []
    for scope in ("public", "private"):
        for ch_id, msgs in shares.get(scope, {}).items():
            if msgs:
                channel_names.append(ch_id)

    return FileResult(
        id=raw.get("id", ""),
        name=raw.get("name", ""),
        title=raw.get("title", "") or raw.get("name", ""),
        filetype=raw.get("filetype", ""),
        mimetype=raw.get("mimetype", ""),
        size=raw.get("size", 0),
        url_private=raw.get("url_private", ""),
        permalink=raw.get("permalink", ""),
        created=raw.get("created", 0),
        user_id=raw.get("user", ""),
        username=raw.get("username", ""),
        channels=channel_names,
        score=raw.get("score", 0.0),
        preview=raw.get("preview", "") or raw.get("plain_text", ""),
    )

def _parse_channel(raw: dict) -> ChannelResult:
    return ChannelResult(
        id=raw.get("id", ""),
        name=raw.get("name", ""),
        topic=(raw.get("topic") or {}).get("value", ""),
        purpose=(raw.get("purpose") or {}).get("value", ""),
        member_count=raw.get("num_members", 0),
        is_private=raw.get("is_private", False),
        is_archived=raw.get("is_archived", False),
        created=raw.get("created", 0),
        creator=raw.get("creator", ""),
    )

def _parse_user(raw: dict) -> UserResult:
    profile = raw.get("profile", {})
    return UserResult(
        id=raw.get("id", ""),
        name=raw.get("name", ""),
        real_name=raw.get("real_name", "") or profile.get("real_name", ""),
        display_name=profile.get("display_name", ""),
        email=profile.get("email", ""),
        title=profile.get("title", ""),
        phone=profile.get("phone", ""),
        team_id=raw.get("team_id", ""),
        is_admin=raw.get("is_admin", False),
        is_bot=raw.get("is_bot", False),
        tz=raw.get("tz", ""),
        status_text=profile.get("status_text", ""),
        avatar_url=profile.get("image_72", ""),
    )


# ── Query builder ─────────────────────────────────────────────────────────────

def build_query(
    q: str,
    *,
    in_: Optional[list[str]] = None,          # in:#channel or in:@user
    from_: Optional[str] = None,              # from:@username
    to_: Optional[str] = None,               # to:@username or to:#channel
    before: Optional[str] = None,            # before:YYYY-MM-DD
    after: Optional[str] = None,             # after:YYYY-MM-DD
    on: Optional[str] = None,               # on:YYYY-MM-DD
    has: Optional[list[str]] = None,         # has:link / has:reaction / has:star
    is_: Optional[list[str]] = None,         # is:dm / is:thread
    with_: Optional[list[str]] = None,       # with:@user (DM partner)
    filetype: Optional[str] = None,          # for file search: pdf, doc, png…
) -> str:
    """
    Programmatically build a Slack search query string.

    Slack search modifier reference:
      in:#channel      → search in specific channel
      from:@user       → messages from a user
      before/after/on  → date filters (YYYY-MM-DD)
      has:link         → messages with links
      has:reaction     → messages that received reactions
      is:dm            → direct messages only
      is:thread        → thread replies only

    Example:
        build_query("payment failed", from_="aditya", in_=["#payments", "#alerts"],
                    after="2024-01-01", has=["link"])
        → 'payment failed from:aditya in:#payments in:#alerts after:2024-01-01 has:link'
    """
    parts = [q.strip()]
    for ch in (in_ or []):
        parts.append(f"in:{ch}")
    if from_:
        parts.append(f"from:{from_}")
    if to_:
        parts.append(f"to:{to_}")
    if before:
        parts.append(f"before:{before}")
    if after:
        parts.append(f"after:{after}")
    if on:
        parts.append(f"on:{on}")
    for h in (has or []):
        parts.append(f"has:{h}")
    for qualifier in (is_ or []):
        parts.append(f"is:{qualifier}")
    for u in (with_ or []):
        parts.append(f"with:{u}")
    if filetype:
        parts.append(f"filetype:{filetype}")
    return " ".join(parts)


# ── Main engine ───────────────────────────────────────────────────────────────

class SlackSearchEngine:
    """
    Corporate-grade Slack search engine with token rotation.
    Zero storage — pure search results returned as Python objects.

    Args:
        tokens:  List of Slack user tokens (xoxp-...).
                 Bot tokens (xoxb-) can't search messages — use user tokens.
                 Pass one token per workspace to search across multiple orgs.
        timeout: HTTP timeout in seconds.
        retries: Retries on transient failures.

    Required OAuth scopes (user token):
        search:read          → messages + files
        channels:read        → public channel listing
        users:read           → user listing
        users:read.email     → include email in user results
    """

    def __init__(
        self,
        tokens: list[str],
        timeout: int = 10,
        retries: int = 2,
    ):
        self._pool = _TokenPool(tokens)
        self._timeout = timeout
        self._retries = retries
        self._session = requests.Session()

    # ── Public API ────────────────────────────────────────────────────────────

    def search(
        self,
        q: str,
        kind: SearchKind = "messages",
        *,
        sort: str = "score",
        sort_dir: Literal["asc", "desc"] = "desc",
        limit: int = 20,
        page: int = 1,
    ) -> SearchResponse:
        """
        Search Slack. Returns a SearchResponse with typed result objects.

        Args:
            q:        Slack search query (supports full modifier syntax).
            kind:     messages · files · all · channels · users
            sort:     "score" (relevance) or "timestamp"
            sort_dir: "asc" or "desc"
            limit:    Results per page (max 100).
            page:     Page number for pagination.

        Raises:
            RateLimitError   — all tokens exhausted
            AuthError        — invalid token
            ScopeError       — token missing required scope
            SearchSyntaxError — malformed query
        """
        if not q.strip() and kind not in ("channels", "users"):
            raise SearchSyntaxError("Query cannot be empty.")

        limit = max(1, min(limit, 100))

        t0 = time.monotonic()

        if kind in ("messages", "files", "all"):
            data = self._slack_search(q, kind, sort, sort_dir, limit, page)
        elif kind == "channels":
            data = self._list_channels(q, limit, page)
        elif kind == "users":
            data = self._list_users(q, limit, page)
        else:
            raise SearchSyntaxError(f"Unknown kind: {kind!r}")

        elapsed = int((time.monotonic() - t0) * 1000)

        # Parse results
        items, total, page_count = self._extract(data, kind, limit)

        return SearchResponse(
            kind=kind,
            query=q,
            total_count=total,
            items=items,
            page=page,
            per_page=limit,
            page_count=page_count,
            elapsed_ms=elapsed,
            token_status=self._pool.status,
        )

    def search_all_pages(
        self,
        q: str,
        kind: SearchKind = "messages",
        *,
        sort: str = "timestamp",
        sort_dir: Literal["asc", "desc"] = "desc",
        max_results: int = 500,
    ) -> SearchResponse:
        """Auto-paginate up to max_results, with polite delay between pages."""
        per_page = min(100, max_results)
        all_items: list[Any] = []
        page = 1
        last: Optional[SearchResponse] = None

        while len(all_items) < max_results:
            resp = self.search(q, kind, sort=sort, sort_dir=sort_dir, limit=per_page, page=page)
            last = resp
            all_items.extend(resp.items)
            if not resp.has_more or not resp.items:
                break
            page += 1
            time.sleep(1.2)   # Slack Tier 2 = 20 req/min → ~3s safe gap

        if last:
            last.items = all_items[:max_results]
        return last  # type: ignore[return-value]

    def multi_search(
        self,
        queries: list[str],
        kind: SearchKind = "messages",
        limit_each: int = 10,
    ) -> list[SearchResponse]:
        """Run multiple queries, auto-handling rate limits between them."""
        results = []
        for q in queries:
            try:
                resp = self.search(q, kind, limit=limit_each)
                results.append(resp)
            except RateLimitError as e:
                print(f"⚠️  Rate limit: {e}. Waiting {e.retry_after:.0f}s…")
                time.sleep(e.retry_after)
                results.append(self.search(q, kind, limit=limit_each))
            time.sleep(1.2)
        return results

    @property
    def token_status(self) -> list[dict]:
        return self._pool.status

    def resolve_workspaces(self) -> list[dict]:
        """
        Resolve the workspace name/domain for each token.
        Calls auth.test once per token and caches the result.
        """
        out = []
        for tok in self._pool._pool:
            try:
                resp = self._session.get(
                    f"{SLACK_API}/auth.test",
                    headers={"Authorization": f"Bearer {tok.value}"},
                    timeout=self._timeout,
                )
                data = resp.json()
                if data.get("ok"):
                    tok.workspace = data.get("team", "")
                    out.append({
                        "token_prefix": tok.value[:14] + "…",
                        "workspace": data.get("team"),
                        "team_id": data.get("team_id"),
                        "url": data.get("url"),
                        "user": data.get("user"),
                        "bot_id": data.get("bot_id"),
                    })
                else:
                    out.append({"token_prefix": tok.value[:14] + "…",
                                "error": data.get("error", "unknown")})
            except Exception as e:
                out.append({"token_prefix": tok.value[:14] + "…", "error": str(e)})
        return out

    # ── Internal: Slack search endpoints ─────────────────────────────────────

    def _slack_search(self, q, kind, sort, sort_dir, count, page) -> dict:
        endpoint = {
            "messages": "search.messages",
            "files":    "search.files",
            "all":      "search.all",
        }[kind]
        params = {
            "query":    q,
            "sort":     sort,
            "sort_dir": sort_dir,
            "count":    count,
            "page":     page,
            "highlight": True,
        }
        return self._request(endpoint, params)

    def _list_channels(self, q: str, limit: int, page: int) -> dict:
        """conversations.list filtered client-side by query."""
        params = {
            "types":            "public_channel,private_channel",
            "exclude_archived": False,
            "limit":            min(limit * 5, 200),  # fetch extra, filter down
        }
        data = self._request("conversations.list", params)
        channels = data.get("channels", [])
        if q:
            q_lower = q.lower()
            channels = [
                c for c in channels
                if q_lower in c.get("name", "").lower()
                or q_lower in (c.get("topic", {}) or {}).get("value", "").lower()
                or q_lower in (c.get("purpose", {}) or {}).get("value", "").lower()
            ]
        # Manual pagination
        start = (page - 1) * limit
        data["_filtered"] = channels[start:start + limit]
        data["_total"] = len(channels)
        return data

    def _list_users(self, q: str, limit: int, page: int) -> dict:
        """users.list filtered client-side by query."""
        params = {"limit": 200}
        data = self._request("users.list", params)
        members = data.get("members", [])
        if q:
            q_lower = q.lower()
            members = [
                m for m in members
                if not m.get("deleted")
                and (
                    q_lower in m.get("name", "").lower()
                    or q_lower in m.get("real_name", "").lower()
                    or q_lower in (m.get("profile", {}) or {}).get("display_name", "").lower()
                    or q_lower in (m.get("profile", {}) or {}).get("email", "").lower()
                    or q_lower in (m.get("profile", {}) or {}).get("title", "").lower()
                )
            ]
        start = (page - 1) * limit
        data["_filtered"] = members[start:start + limit]
        data["_total"] = len(members)
        return data

    # ── Result extraction ─────────────────────────────────────────────────────

    def _extract(self, data: dict, kind: SearchKind, per_page: int):
        if kind == "messages":
            block = data.get("messages", {})
            paging = block.get("paging", {})
            return (
                [_parse_message(m) for m in block.get("matches", [])],
                paging.get("total", 0),
                paging.get("pages", 1),
            )
        if kind == "files":
            block = data.get("files", {})
            paging = block.get("paging", {})
            return (
                [_parse_file(f) for f in block.get("matches", [])],
                paging.get("total", 0),
                paging.get("pages", 1),
            )
        if kind == "all":
            msgs  = data.get("messages", {}).get("matches", [])
            files = data.get("files",    {}).get("matches", [])
            total = (data.get("messages", {}).get("paging", {}).get("total", 0) +
                     data.get("files",    {}).get("paging", {}).get("total", 0))
            items = [_parse_message(m) for m in msgs] + [_parse_file(f) for f in files]
            return items, total, max(1, total // per_page)
        if kind == "channels":
            items = [_parse_channel(c) for c in data.get("_filtered", [])]
            total = data.get("_total", len(items))
            return items, total, max(1, total // per_page)
        if kind == "users":
            items = [_parse_user(u) for u in data.get("_filtered", [])]
            total = data.get("_total", len(items))
            return items, total, max(1, total // per_page)
        return [], 0, 1

    # ── HTTP layer ─────────────────────────────────────────────────────────────

    def _request(self, method: str, params: dict) -> dict:
        url = f"{SLACK_API}/{method}"
        last_error: Optional[Exception] = None

        for attempt in range(self._retries + 1):
            tok = self._pool.acquire()
            headers = {
                "Authorization": f"Bearer {tok.value}",
                "Content-Type":  "application/x-www-form-urlencoded",
            }
            try:
                resp = self._session.get(
                    url, params=params, headers=headers, timeout=self._timeout
                )

                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", 60))
                    self._pool.penalize(tok)
                    raise RateLimitError(
                        f"Slack rate limit on {method}.", retry_after=retry_after
                    )

                resp.raise_for_status()
                data = resp.json()
                self._pool.record(tok)

                if not data.get("ok"):
                    error = data.get("error", "unknown_error")

                    if error in ("invalid_auth", "token_revoked", "not_authed"):
                        self._pool.penalize(tok)
                        raise AuthError(f"Token rejected by Slack: {error}")

                    if error in ("missing_scope", "no_permission"):
                        raise ScopeError(
                            f"Token lacks required scope for {method}. "
                            f"Add 'search:read' (and 'users:read' for user search) "
                            f"to your Slack app's OAuth scopes."
                        )

                    if error == "ratelimited":
                        retry_after = float(data.get("retry_after", 60))
                        raise RateLimitError(f"Slack ratelimited: {method}", retry_after=retry_after)

                    if error in ("query_too_long", "invalid_query"):
                        raise SearchSyntaxError(f"Invalid Slack query: {error}")

                    raise SlackSearchError(f"Slack API error [{method}]: {error}")

                return data

            except (AuthError, ScopeError, SearchSyntaxError, RateLimitError):
                raise
            except requests.RequestException as e:
                last_error = SlackSearchError(f"Network error: {e}")
                self._pool.penalize(tok)
                time.sleep(1.5 ** attempt)
                continue

        raise last_error or SlackSearchError(f"Request failed after {self._retries} retries.")


# ── FastAPI integration ───────────────────────────────────────────────────────
# Drop-in for TracePath backend: from services.slack_search import router

try:
    from fastapi import APIRouter, Query, HTTPException, Header
    from pydantic import BaseModel as _BaseModel
    import os

    router = APIRouter(tags=["Slack Search"])
    _engine: Optional[SlackSearchEngine] = None

    class TokenConfig(_BaseModel):
        tokens: list[str]

    def _env_tokens() -> list[str]:
        raw = os.getenv("SLACK_TOKENS") or ""
        if raw.strip():
            return [t.strip() for t in raw.split(",") if t.strip()]
        single = os.getenv("SLACK_TOKEN")
        return [single] if single else []

    @router.post("/search/slack/configure")
    def configure_tokens(cfg: TokenConfig):
        global _engine
        _engine = SlackSearchEngine(cfg.tokens)
        workspaces = _engine.resolve_workspaces()
        return {"status": "ok", "token_count": len(cfg.tokens), "workspaces": workspaces}

    @router.get("/search/slack")
    def slack_search(
        q: str = Query("", description="Slack search query (use build_query() helper for modifiers)"),
        kind: SearchKind = Query("messages"),
        sort: str = Query("score"),
        sort_dir: Literal["asc", "desc"] = Query("desc"),
        limit: int = Query(20, ge=1, le=100),
        page: int = Query(1, ge=1),
        x_slack_token: str | None = Header(default=None, alias="X-Slack-Token"),
    ):
        engine = _engine
        if x_slack_token:
            engine = SlackSearchEngine([x_slack_token])
        if engine is None:
            env_tokens = _env_tokens()
            if env_tokens:
                engine = SlackSearchEngine(env_tokens)
        if engine is None:
            raise HTTPException(422, "No tokens configured. Set SLACK_TOKEN or POST /search/slack/configure.")
        try:
            return engine.search(q, kind, sort=sort, sort_dir=sort_dir, limit=limit, page=page).to_dict()
        except RateLimitError as e:
            raise HTTPException(429, str(e))
        except AuthError as e:
            raise HTTPException(401, str(e))
        except ScopeError as e:
            raise HTTPException(403, str(e))
        except SearchSyntaxError as e:
            raise HTTPException(400, str(e))
        except SlackSearchError as e:
            raise HTTPException(502, str(e))

    @router.get("/search/slack/tokens/status")
    def token_status():
        if _engine is None:
            raise HTTPException(422, "No tokens configured.")
        return _engine.token_status

    @router.get("/search/slack/workspaces")
    def workspaces():
        if _engine is None:
            raise HTTPException(422, "No tokens configured.")
        return _engine.resolve_workspaces()

except ImportError:
    pass   # FastAPI not installed — standalone mode only


# ── CLI / quick demo ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys, os

    token = os.getenv("SLACK_TOKEN") or (sys.argv[1] if len(sys.argv) > 1 else None)
    query = sys.argv[2] if len(sys.argv) > 2 else "payment error"
    kind  = sys.argv[3] if len(sys.argv) > 3 else "messages"

    if not token:
        print("Usage: python slack_search.py <xoxp-token> [query] [kind]")
        print("   or: SLACK_TOKEN=xoxp-... python slack_search.py")
        sys.exit(1)

    engine = SlackSearchEngine(tokens=[token])

    print(f"\n🔍 Checking workspace…")
    for ws in engine.resolve_workspaces():
        print(f"  ✅ {ws.get('workspace')} ({ws.get('url', '')})")

    print(f"\n🔍 Searching Slack [{kind}]: {query!r}\n")
    resp = engine.search(query, kind=kind, limit=5)  # type: ignore[arg-type]
    print(f"  {resp.total_count:,} total results  ·  {resp.elapsed_ms}ms\n")

    for item in resp.items:
        d = vars(item)
        if kind == "messages":
            print(f"  [{d.get('channel_name','dm')}] {d.get('username','')}:")
            text = d.get("text", "")[:120].replace("\n", " ")
            print(f"    {text}")
            print(f"    {d.get('permalink','')}")
        elif kind == "files":
            print(f"  {d.get('name','')} ({d.get('filetype','')}, {d.get('size',0)//1024}KB)")
            print(f"    by {d.get('username','')}  ·  {d.get('permalink','')}")
        elif kind == "channels":
            priv = "🔒" if d.get("is_private") else "#"
            print(f"  {priv}{d.get('name','')}  ({d.get('member_count',0)} members)")
            print(f"    {d.get('purpose','')[:80]}")
        elif kind == "users":
            print(f"  @{d.get('name','')}  —  {d.get('real_name','')}")
            print(f"    {d.get('title','')}  ·  {d.get('email','')}")
        print()
