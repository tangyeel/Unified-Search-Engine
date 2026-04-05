"""
gdrive_search.py — TracePath Google Drive Search Engine
Pure search layer. No storage. No graph. Just fast, ranked results.

Supports: files · folders · shared drives · comments · revisions
Token rotation built-in — pass multiple OAuth tokens to span accounts/domains.

Auth options:
  1. OAuth2 access token   (personal account — expires in 1h, use refresh token)
  2. Service account JWT   (corporate G Suite / Workspace — recommended for orgs)

Usage:
    engine = GDriveSearchEngine(tokens=["ya29.aaa", "ya29.bbb"])
    results = engine.search("payment invoice", kind="files", limit=20)
"""

import requests
import time
import threading
import json
from typing import Optional, Literal, Any
from dataclasses import dataclass, field

# ── Types ─────────────────────────────────────────────────────────────────────

SearchKind = Literal["files", "folders", "shared_drives", "comments", "revisions"]

GOOGLE_API      = "https://www.googleapis.com/drive/v3"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# Google Drive MIME types for human-readable labels
MIME_LABELS: dict[str, str] = {
    "application/vnd.google-apps.document":     "Google Doc",
    "application/vnd.google-apps.spreadsheet":  "Google Sheet",
    "application/vnd.google-apps.presentation": "Google Slides",
    "application/vnd.google-apps.form":         "Google Form",
    "application/vnd.google-apps.folder":       "Folder",
    "application/vnd.google-apps.shortcut":     "Shortcut",
    "application/pdf":                          "PDF",
    "application/zip":                          "ZIP",
    "text/plain":                               "Text",
    "text/csv":                                 "CSV",
    "image/png":                                "PNG",
    "image/jpeg":                               "JPEG",
    "video/mp4":                                "MP4",
}

MAX_PAGE_SIZE = 1000   # Drive API hard cap per page


# ── Token pool ────────────────────────────────────────────────────────────────

@dataclass
class _Token:
    value: str                       # OAuth access token or service account JWT
    refresh_token: str = ""          # for auto-refresh
    client_id: str = ""
    client_secret: str = ""
    expires_at: float = float("inf") # unix ts
    failures: int = 0
    email: str = ""                  # resolved on first use
    domain: str = ""

    @property
    def expired(self) -> bool:
        return time.time() > self.expires_at - 30   # 30s buffer

    @property
    def healthy(self) -> bool:
        return self.failures < 3

    @property
    def can_refresh(self) -> bool:
        return bool(self.refresh_token and self.client_id and self.client_secret)


class _TokenPool:
    """OAuth token pool with auto-refresh support."""

    def __init__(self, tokens: list):
        """
        tokens: list of either —
          str                           → raw access token (no refresh)
          dict with keys:
            access_token, refresh_token, client_id, client_secret, expires_at (optional)
          OR a service_account dict:
            type: "service_account", ...standard service account JSON fields...
        """
        if not tokens:
            raise ValueError("Provide at least one token.")
        self._pool: list[_Token] = []
        self._lock = threading.Lock()
        self._session = requests.Session()

        for t in tokens:
            if isinstance(t, str):
                self._pool.append(_Token(value=t.strip()))
            elif isinstance(t, dict):
                if t.get("type") == "service_account":
                    # Will exchange for access token on first use
                    tok = _Token(value="", refresh_token="__service_account__")
                    tok._sa_info = t  # stash for JWT exchange
                    self._pool.append(tok)
                else:
                    self._pool.append(_Token(
                        value=t.get("access_token", ""),
                        refresh_token=t.get("refresh_token", ""),
                        client_id=t.get("client_id", ""),
                        client_secret=t.get("client_secret", ""),
                        expires_at=float(t.get("expires_at", float("inf"))),
                    ))

    def acquire(self) -> "_Token":
        with self._lock:
            healthy = [t for t in self._pool if t.healthy]
            if not healthy:
                raise RateLimitError("All tokens unhealthy/exhausted.", retry_after=60)

            # Prefer non-expired tokens; auto-refresh if possible
            for tok in healthy:
                if not tok.expired:
                    return tok
                if tok.can_refresh:
                    self._refresh(tok)
                    return tok

            raise RateLimitError("All tokens expired and cannot be refreshed.", retry_after=300)

    def _refresh(self, tok: "_Token"):
        """Exchange refresh token for new access token (standard OAuth2)."""
        try:
            resp = self._session.post(GOOGLE_TOKEN_URL, data={
                "client_id":     tok.client_id,
                "client_secret": tok.client_secret,
                "refresh_token": tok.refresh_token,
                "grant_type":    "refresh_token",
            }, timeout=10)
            data = resp.json()
            tok.value = data["access_token"]
            tok.expires_at = time.time() + data.get("expires_in", 3600)
            tok.failures = 0
            print(f"🔄 Token refreshed for {tok.email or tok.value[:20]}…")
        except Exception as e:
            tok.failures += 1
            raise AuthError(f"Token refresh failed: {e}")

    def penalize(self, tok: "_Token"):
        with self._lock:
            tok.failures += 1

    def reset(self, tok: "_Token"):
        with self._lock:
            tok.failures = 0

    @property
    def status(self) -> list[dict]:
        return [
            {
                "token_prefix":  t.value[:20] + "…" if t.value else "(service account)",
                "email":         t.email or "unknown",
                "domain":        t.domain or "unknown",
                "expired":       t.expired,
                "can_refresh":   t.can_refresh,
                "healthy":       t.healthy,
                "failures":      t.failures,
            }
            for t in self._pool
        ]


# ── Exceptions ────────────────────────────────────────────────────────────────

class GDriveSearchError(Exception):
    pass

class RateLimitError(GDriveSearchError):
    def __init__(self, msg: str, retry_after: float = 60):
        super().__init__(msg)
        self.retry_after = retry_after

class AuthError(GDriveSearchError):
    pass

class ScopeError(GDriveSearchError):
    pass

class SearchSyntaxError(GDriveSearchError):
    pass


# ── Result dataclasses ────────────────────────────────────────────────────────

@dataclass
class FileResult:
    id: str
    name: str
    mime_type: str
    kind: str                     # human label from MIME_LABELS
    description: str
    created_time: str
    modified_time: str
    size: int                     # bytes (0 for Google native types)
    owners: list[str]             # display names
    shared_with_me: bool
    starred: bool
    trashed: bool
    parents: list[str]            # parent folder IDs
    web_view_link: str
    web_content_link: str
    thumbnail_link: str
    shared_drive_id: str
    permissions_summary: str      # "anyone" | "domain" | "specific"
    full_text_snippet: str        # from Drive full-text index when available

@dataclass
class FolderResult:
    id: str
    name: str
    created_time: str
    modified_time: str
    owners: list[str]
    parent_id: str
    web_view_link: str
    shared_drive_id: str
    item_count: int               # -1 = not fetched (requires extra API call)

@dataclass
class SharedDriveResult:
    id: str
    name: str
    created_time: str
    capabilities: dict            # what the current user can do
    theme_color_rgb: str

@dataclass
class CommentResult:
    id: str
    file_id: str
    file_name: str
    content: str
    author: str
    author_email: str
    created_time: str
    modified_time: str
    resolved: bool
    replies: list[str]            # reply content strings

@dataclass
class RevisionResult:
    id: str
    file_id: str
    file_name: str
    mime_type: str
    modified_time: str
    last_modifying_user: str
    keep_forever: bool
    published: bool

@dataclass
class SearchResponse:
    kind: SearchKind
    query: str
    total_count: int              # Drive doesn't give exact totals; this is len(items) or estimated
    items: list[Any]
    page: int
    per_page: int
    next_page_token: Optional[str]
    elapsed_ms: int
    token_status: list[dict] = field(default_factory=list)

    @property
    def has_more(self) -> bool:
        return self.next_page_token is not None

    def to_dict(self) -> dict:
        def _s(obj):
            return vars(obj) if hasattr(obj, "__dataclass_fields__") else obj
        return {
            "kind":            self.kind,
            "query":           self.query,
            "total_count":     self.total_count,
            "page":            self.page,
            "per_page":        self.per_page,
            "next_page_token": self.next_page_token,
            "has_more":        self.has_more,
            "elapsed_ms":      self.elapsed_ms,
            "items":           [_s(i) for i in self.items],
            "token_status":    self.token_status,
        }


# ── Parsers ───────────────────────────────────────────────────────────────────

def _owners(raw: dict) -> list[str]:
    return [o.get("displayName", o.get("emailAddress", "")) for o in raw.get("owners", [])]

def _perm_summary(raw: dict) -> str:
    perms = raw.get("permissions", [])
    for p in perms:
        if p.get("type") == "anyone":
            return "anyone"
        if p.get("type") == "domain":
            return "domain"
    return "specific" if perms else "private"

def _parse_file(raw: dict) -> FileResult:
    mime = raw.get("mimeType", "")
    return FileResult(
        id=raw.get("id", ""),
        name=raw.get("name", ""),
        mime_type=mime,
        kind=MIME_LABELS.get(mime, mime.split("/")[-1]),
        description=raw.get("description", "") or "",
        created_time=raw.get("createdTime", ""),
        modified_time=raw.get("modifiedTime", ""),
        size=int(raw.get("size", 0) or 0),
        owners=_owners(raw),
        shared_with_me=raw.get("sharedWithMe", False),
        starred=raw.get("starred", False),
        trashed=raw.get("trashed", False),
        parents=raw.get("parents", []),
        web_view_link=raw.get("webViewLink", ""),
        web_content_link=raw.get("webContentLink", ""),
        thumbnail_link=raw.get("thumbnailLink", ""),
        shared_drive_id=raw.get("driveId", ""),
        permissions_summary=_perm_summary(raw),
        full_text_snippet=raw.get("fullTextSnippet", "") or "",
    )

def _parse_folder(raw: dict) -> FolderResult:
    parents = raw.get("parents", [])
    return FolderResult(
        id=raw.get("id", ""),
        name=raw.get("name", ""),
        created_time=raw.get("createdTime", ""),
        modified_time=raw.get("modifiedTime", ""),
        owners=_owners(raw),
        parent_id=parents[0] if parents else "",
        web_view_link=raw.get("webViewLink", ""),
        shared_drive_id=raw.get("driveId", ""),
        item_count=-1,
    )

def _parse_shared_drive(raw: dict) -> SharedDriveResult:
    bg = raw.get("backgroundImageFile", {}) or {}
    return SharedDriveResult(
        id=raw.get("id", ""),
        name=raw.get("name", ""),
        created_time=raw.get("createdTime", ""),
        capabilities=raw.get("capabilities", {}),
        theme_color_rgb=bg.get("color", ""),
    )

def _parse_comment(raw: dict, file_id: str = "", file_name: str = "") -> CommentResult:
    author = raw.get("author", {}) or {}
    replies = [r.get("content", "") for r in raw.get("replies", [])]
    return CommentResult(
        id=raw.get("id", ""),
        file_id=file_id,
        file_name=file_name,
        content=raw.get("content", ""),
        author=author.get("displayName", ""),
        author_email=author.get("emailAddress", ""),
        created_time=raw.get("createdTime", ""),
        modified_time=raw.get("modifiedTime", ""),
        resolved=raw.get("resolved", False),
        replies=replies,
    )

def _parse_revision(raw: dict, file_id: str = "", file_name: str = "") -> RevisionResult:
    user = (raw.get("lastModifyingUser") or {})
    return RevisionResult(
        id=raw.get("id", ""),
        file_id=file_id,
        file_name=file_name,
        mime_type=raw.get("mimeType", ""),
        modified_time=raw.get("modifiedTime", ""),
        last_modifying_user=user.get("displayName", user.get("emailAddress", "")),
        keep_forever=raw.get("keepForever", False),
        published=raw.get("published", False),
    )


# ── Query builder ─────────────────────────────────────────────────────────────

def build_query(
    q: str = "",
    *,
    name: Optional[str] = None,              # name contains
    name_exact: Optional[str] = None,        # name = exact
    fulltext: Optional[str] = None,          # fullText contains
    mime_type: Optional[str] = None,         # exact MIME type
    mime_contains: Optional[str] = None,     # mimeType contains (e.g. "image")
    not_mime: Optional[str] = None,          # exclude MIME type
    in_folder: Optional[str] = None,         # parent folder ID
    in_drive: Optional[str] = None,          # shared drive ID
    owner: Optional[str] = None,             # owner email/name
    writer: Optional[str] = None,
    reader: Optional[str] = None,
    created_after: Optional[str] = None,     # RFC 3339 e.g. "2024-01-01T00:00:00"
    created_before: Optional[str] = None,
    modified_after: Optional[str] = None,
    modified_before: Optional[str] = None,
    shared_with_me: bool = False,
    starred: bool = False,
    trashed: bool = False,
    is_folder: Optional[bool] = None,        # True=folders only, False=exclude folders
    visibility: Optional[Literal["anyoneCanFind", "anyoneWithLink",
                                  "domainCanFind", "domainWithLink",
                                  "limited"]] = None,
) -> str:
    """
    Build a Google Drive API query string (for the files.list `q` parameter).

    Drive query syntax uses operators: contains, =, !=, <, <=, >=, >
    Clauses are joined with 'and' / 'or' / 'not'.

    Examples:
        build_query("invoice")
        → "fullText contains 'invoice'"

        build_query(name="Q4 Report", modified_after="2024-01-01T00:00:00")
        → "name contains 'Q4 Report' and modifiedTime > '2024-01-01T00:00:00'"

        build_query(mime_type="application/pdf", owner="finance@corp.com", starred=True)
        → "mimeType = 'application/pdf' and 'finance@corp.com' in owners and starred = true"
    """
    def _esc(s: str) -> str:
        return s.replace("'", "\\'")

    clauses: list[str] = []

    if q:
        clauses.append(f"fullText contains '{_esc(q)}'")
    if fulltext:
        clauses.append(f"fullText contains '{_esc(fulltext)}'")
    if name:
        clauses.append(f"name contains '{_esc(name)}'")
    if name_exact:
        clauses.append(f"name = '{_esc(name_exact)}'")
    if mime_type:
        clauses.append(f"mimeType = '{_esc(mime_type)}'")
    if mime_contains:
        clauses.append(f"mimeType contains '{_esc(mime_contains)}'")
    if not_mime:
        clauses.append(f"mimeType != '{_esc(not_mime)}'")
    if is_folder is True:
        clauses.append("mimeType = 'application/vnd.google-apps.folder'")
    elif is_folder is False:
        clauses.append("mimeType != 'application/vnd.google-apps.folder'")
    if in_folder:
        clauses.append(f"'{_esc(in_folder)}' in parents")
    if in_drive:
        clauses.append(f"'{_esc(in_drive)}' in parents")
    if owner:
        clauses.append(f"'{_esc(owner)}' in owners")
    if writer:
        clauses.append(f"'{_esc(writer)}' in writers")
    if reader:
        clauses.append(f"'{_esc(reader)}' in readers")
    if created_after:
        clauses.append(f"createdTime > '{_esc(created_after)}'")
    if created_before:
        clauses.append(f"createdTime < '{_esc(created_before)}'")
    if modified_after:
        clauses.append(f"modifiedTime > '{_esc(modified_after)}'")
    if modified_before:
        clauses.append(f"modifiedTime < '{_esc(modified_before)}'")
    if shared_with_me:
        clauses.append("sharedWithMeTime != null")
    if starred:
        clauses.append("starred = true")
    if trashed:
        clauses.append("trashed = true")
    else:
        clauses.append("trashed = false")
    if visibility:
        clauses.append(f"visibility = '{visibility}'")

    return " and ".join(clauses) if clauses else ""


# ── Field sets (controls which fields Drive API returns) ──────────────────────

FILE_FIELDS = (
    "id,name,mimeType,description,createdTime,modifiedTime,"
    "size,owners,sharedWithMeTime,starred,trashed,parents,"
    "webViewLink,webContentLink,thumbnailLink,driveId,"
    "permissions(type)"
)

LIST_FIELDS = f"nextPageToken,files({FILE_FIELDS})"

DRIVE_FIELDS = "nextPageToken,drives(id,name,createdTime,capabilities,backgroundImageFile)"


# ── Main engine ───────────────────────────────────────────────────────────────

class GDriveSearchEngine:
    """
    Corporate-grade Google Drive search engine with token rotation.
    Zero storage — pure search results returned as Python objects.

    Args:
        tokens:   List of OAuth access tokens (str), OAuth dicts, or
                  service account JSON dicts.
        timeout:  HTTP timeout in seconds.
        retries:  Retries on transient failures.
        include_shared_drives:
                  Whether to search across all shared/team drives.
        corpora:  Drive corpus to search.
                  "user"       → My Drive only
                  "drive"      → specific shared drive (set drive_id)
                  "allDrives"  → My Drive + all shared drives (recommended for orgs)
                  "domain"     → entire G Suite domain (requires admin)

    Required OAuth scopes:
        https://www.googleapis.com/auth/drive.readonly     (full read)
        https://www.googleapis.com/auth/drive.metadata.readonly (metadata only, safer)
    """

    def __init__(
        self,
        tokens: list,
        timeout: int = 12,
        retries: int = 2,
        include_shared_drives: bool = True,
        corpora: Literal["user", "drive", "allDrives", "domain"] = "allDrives",
    ):
        self._pool = _TokenPool(tokens)
        self._timeout = timeout
        self._retries = retries
        self._include_shared = include_shared_drives
        self._corpora = corpora
        self._session = requests.Session()

    # ── Public API ────────────────────────────────────────────────────────────

    def search(
        self,
        q: str,
        kind: SearchKind = "files",
        *,
        order_by: str = "modifiedTime desc",
        limit: int = 30,
        page_token: Optional[str] = None,
        drive_id: Optional[str] = None,      # required when corpora="drive"
    ) -> SearchResponse:
        """
        Search Google Drive. Returns a SearchResponse with typed result objects.

        Args:
            q:          Drive query string. Use build_query() to construct.
                        Plain strings are auto-wrapped as fullText contains '…'
            kind:       files · folders · shared_drives · comments · revisions
            order_by:   Comma-separated sort fields with optional 'desc'.
                        e.g. "modifiedTime desc,name"
                        Valid: createdTime, folder, modifiedByMeTime,
                               modifiedTime, name, name_natural, quotaBytesUsed,
                               recency, sharedWithMeTime, starred, viewedByMeTime
            limit:      Results per page (max 1000 for files, 100 for drives).
            page_token: Pass SearchResponse.next_page_token to get the next page.
            drive_id:   Shared drive ID (only needed when corpora="drive").

        Raises:
            RateLimitError    — quota exceeded
            AuthError         — token invalid
            ScopeError        — missing OAuth scope
            SearchSyntaxError — malformed query
        """
        # Auto-wrap plain text as fullText query
        if q and not any(op in q for op in ["contains", "=", "in ", "trashed"]):
            q = f"fullText contains '{q.replace(chr(39), chr(92)+chr(39))}' and trashed = false"
        elif not q:
            q = "trashed = false"

        t0 = time.monotonic()

        if kind == "files":
            data, npt = self._list_files(q, order_by, limit, page_token, drive_id, folders=False)
            items = [_parse_file(f) for f in data]
        elif kind == "folders":
            folder_q = f"mimeType = 'application/vnd.google-apps.folder' and {q}"
            data, npt = self._list_files(folder_q, order_by, limit, page_token, drive_id, folders=True)
            items = [_parse_folder(f) for f in data]
        elif kind == "shared_drives":
            data, npt = self._list_drives(q, limit, page_token)
            items = [_parse_shared_drive(d) for d in data]
        elif kind == "comments":
            data, npt = self._search_comments(q, limit)
            items = data
        elif kind == "revisions":
            data, npt = self._search_revisions(q, limit)
            items = data
        else:
            raise SearchSyntaxError(f"Unknown kind: {kind!r}")

        elapsed = int((time.monotonic() - t0) * 1000)
        return SearchResponse(
            kind=kind,
            query=q,
            total_count=len(items),
            items=items,
            page=1,
            per_page=limit,
            next_page_token=npt,
            elapsed_ms=elapsed,
            token_status=self._pool.status,
        )

    def search_all_pages(
        self,
        q: str,
        kind: SearchKind = "files",
        *,
        order_by: str = "modifiedTime desc",
        max_results: int = 1000,
        drive_id: Optional[str] = None,
    ) -> SearchResponse:
        """Auto-paginate using nextPageToken until max_results reached."""
        all_items: list[Any] = []
        page_token: Optional[str] = None
        last: Optional[SearchResponse] = None
        page = 0

        while len(all_items) < max_results:
            limit = min(MAX_PAGE_SIZE, max_results - len(all_items))
            resp = self.search(q, kind, order_by=order_by, limit=limit,
                               page_token=page_token, drive_id=drive_id)
            last = resp
            all_items.extend(resp.items)
            page_token = resp.next_page_token
            page += 1
            if not page_token or not resp.items:
                break
            time.sleep(0.3)

        if last:
            last.items = all_items
            last.total_count = len(all_items)
            last.page = page
        return last  # type: ignore[return-value]

    def multi_search(
        self,
        queries: list[str],
        kind: SearchKind = "files",
        limit_each: int = 20,
    ) -> list[SearchResponse]:
        """Run multiple Drive queries, auto-handling quota errors."""
        results = []
        for q in queries:
            try:
                results.append(self.search(q, kind, limit=limit_each))
            except RateLimitError as e:
                print(f"⚠️  Quota hit: {e}. Waiting {e.retry_after:.0f}s…")
                time.sleep(e.retry_after)
                results.append(self.search(q, kind, limit=limit_each))
            time.sleep(0.5)
        return results

    def resolve_accounts(self) -> list[dict]:
        """
        Identify each token's Google account via the tokeninfo endpoint.
        Call this on startup to verify tokens and cache emails.
        """
        out = []
        for tok in self._pool._pool:
            try:
                resp = self._session.get(
                    "https://www.googleapis.com/oauth2/v3/tokeninfo",
                    params={"access_token": tok.value},
                    timeout=8,
                )
                data = resp.json()
                if "error" not in data:
                    tok.email = data.get("email", "")
                    tok.domain = tok.email.split("@")[-1] if "@" in tok.email else ""
                    out.append({
                        "token_prefix": tok.value[:20] + "…",
                        "email": tok.email,
                        "domain": tok.domain,
                        "scope": data.get("scope", ""),
                        "expires_in": data.get("expires_in"),
                    })
                else:
                    out.append({"token_prefix": tok.value[:20] + "…",
                                "error": data.get("error_description", data.get("error"))})
            except Exception as e:
                out.append({"token_prefix": tok.value[:20] + "…", "error": str(e)})
        return out

    @property
    def token_status(self) -> list[dict]:
        return self._pool.status

    # ── Internal: Drive API calls ─────────────────────────────────────────────

    def _list_files(self, q, order_by, limit, page_token, drive_id, folders=False):
        params: dict[str, Any] = {
            "q":               q,
            "orderBy":         order_by,
            "pageSize":        min(limit, MAX_PAGE_SIZE),
            "fields":          LIST_FIELDS,
            "supportsAllDrives":       self._include_shared,
            "includeItemsFromAllDrives": self._include_shared,
            "corpora":         self._corpora,
        }
        if page_token:
            params["pageToken"] = page_token
        if drive_id:
            params["driveId"] = drive_id
            params["corpora"] = "drive"

        data = self._request("files", params)
        return data.get("files", []), data.get("nextPageToken")

    def _list_drives(self, q, limit, page_token):
        params: dict[str, Any] = {
            "pageSize": min(limit, 100),
            "fields":   DRIVE_FIELDS,
            "useDomainAdminAccess": False,
        }
        if q and "trashed" not in q:
            params["q"] = q
        if page_token:
            params["pageToken"] = page_token
        data = self._request("drives", params)
        return data.get("drives", []), data.get("nextPageToken")

    def _search_comments(self, q: str, limit: int):
        """
        Drive API doesn't have a comments search endpoint — we find
        recently modified files and fetch their comments.
        """
        file_q = f"modifiedTime > '2020-01-01T00:00:00' and trashed = false"
        files, _ = self._list_files(file_q, "modifiedTime desc", min(limit, 20), None, None)

        all_comments: list[CommentResult] = []
        q_lower = q.replace("fullText contains '", "").replace("'", "").strip().lower()

        for f in files:
            if len(all_comments) >= limit:
                break
            try:
                data = self._request(
                    f"files/{f['id']}/comments",
                    {"fields": "comments(id,content,author,createdTime,modifiedTime,resolved,replies)",
                     "pageSize": 20},
                )
                for c in data.get("comments", []):
                    content = c.get("content", "").lower()
                    replies_text = " ".join(r.get("content", "") for r in c.get("replies", []))
                    if not q_lower or q_lower in content or q_lower in replies_text.lower():
                        all_comments.append(_parse_comment(c, f["id"], f.get("name", "")))
            except Exception:
                continue

        return all_comments[:limit], None

    def _search_revisions(self, q: str, limit: int):
        """Find recently modified files and list their revisions."""
        file_q = f"modifiedTime > '2020-01-01T00:00:00' and trashed = false"
        files, _ = self._list_files(file_q, "modifiedTime desc", min(limit, 15), None, None)

        all_revisions: list[RevisionResult] = []
        q_lower = q.replace("fullText contains '", "").replace("'", "").strip().lower()

        for f in files:
            if len(all_revisions) >= limit:
                break
            try:
                data = self._request(
                    f"files/{f['id']}/revisions",
                    {"fields": "revisions(id,mimeType,modifiedTime,lastModifyingUser,keepForever,published)"},
                )
                for r in data.get("revisions", []):
                    user = (r.get("lastModifyingUser") or {})
                    user_name = user.get("displayName", user.get("emailAddress", "")).lower()
                    if not q_lower or q_lower in f.get("name", "").lower() or q_lower in user_name:
                        all_revisions.append(_parse_revision(r, f["id"], f.get("name", "")))
            except Exception:
                continue

        return all_revisions[:limit], None

    # ── HTTP layer ────────────────────────────────────────────────────────────

    def _request(self, endpoint: str, params: dict) -> dict:
        url = f"{GOOGLE_API}/{endpoint}"
        last_error: Optional[Exception] = None

        for attempt in range(self._retries + 1):
            tok = self._pool.acquire()
            headers = {"Authorization": f"Bearer {tok.value}"}
            try:
                resp = self._session.get(url, params=params, headers=headers,
                                         timeout=self._timeout)

                if resp.status_code == 200:
                    self._pool.reset(tok)
                    return resp.json()

                body = {}
                try:
                    body = resp.json()
                except Exception:
                    pass
                err = (body.get("error") or {})
                msg = err.get("message", "") if isinstance(err, dict) else str(err)
                code = err.get("code", resp.status_code) if isinstance(err, dict) else resp.status_code
                errors = err.get("errors", []) if isinstance(err, dict) else []
                reason = errors[0].get("reason", "") if errors else ""

                if resp.status_code == 401:
                    self._pool.penalize(tok)
                    if tok.can_refresh:
                        self._pool._refresh(tok)
                        continue
                    raise AuthError(f"Token rejected (401): {msg}")

                if resp.status_code == 403:
                    if reason in ("rateLimitExceeded", "userRateLimitExceeded"):
                        retry_after = float(resp.headers.get("Retry-After", 60))
                        raise RateLimitError(f"Quota exceeded: {msg}", retry_after=retry_after)
                    if reason in ("insufficientFilePermissions", "forbidden"):
                        raise ScopeError(f"Missing permission: {msg}. Ensure drive.readonly scope.")
                    raise GDriveSearchError(f"Forbidden: {msg}")

                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", 60))
                    raise RateLimitError(f"Too many requests: {msg}", retry_after=retry_after)

                if resp.status_code == 400:
                    raise SearchSyntaxError(f"Invalid Drive query: {msg}")

                if resp.status_code in (500, 503):
                    last_error = GDriveSearchError(f"Drive API unavailable ({resp.status_code})")
                    time.sleep(2 ** attempt)
                    continue

                raise GDriveSearchError(f"Drive API {resp.status_code}: {msg}")

            except (AuthError, ScopeError, SearchSyntaxError, RateLimitError):
                raise
            except requests.RequestException as e:
                last_error = GDriveSearchError(f"Network error: {e}")
                self._pool.penalize(tok)
                time.sleep(1.5 ** attempt)
                continue

        raise last_error or GDriveSearchError("Request failed after retries.")


# ── FastAPI integration ───────────────────────────────────────────────────────
# from services.gdrive_search import router

try:
    from fastapi import APIRouter, Query as FQuery, HTTPException, Header
    from pydantic import BaseModel as _BaseModel
    import os

    router = APIRouter(tags=["Google Drive Search"])
    _engine: Optional[GDriveSearchEngine] = None

    class TokenConfig(_BaseModel):
        tokens: list            # str | dict (OAuth) | dict (service account)
        include_shared_drives: bool = True
        corpora: str = "allDrives"

    def _env_tokens():
        # 1) Refresh-token flow (recommended for production)
        refresh_token = os.getenv("GDRIVE_REFRESH_TOKEN")
        client_id = os.getenv("GDRIVE_CLIENT_ID")
        client_secret = os.getenv("GDRIVE_CLIENT_SECRET")
        if refresh_token and client_id and client_secret:
            return [{
                "access_token": "",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "expires_at": 0,
            }]

        # 2) Token list (comma-separated access tokens)
        raw = os.getenv("GDRIVE_TOKENS") or ""
        if raw.strip():
            return [t.strip() for t in raw.split(",") if t.strip()]

        # 3) Single access token
        single = os.getenv("GDRIVE_TOKEN")
        return [single] if single else []

    def _ensure_engine():
        global _engine
        if _engine is None:
            env_tokens = _env_tokens()
            if env_tokens:
                _engine = GDriveSearchEngine(env_tokens)
        return _engine

    def _refresh_if_needed(engine: "GDriveSearchEngine"):
        for tok in engine._pool._pool:
            if tok.expired and tok.can_refresh:
                try:
                    engine._pool._refresh(tok)
                except Exception:
                    continue

    @router.post("/search/gdrive/configure")
    def configure(cfg: TokenConfig):
        global _engine
        _engine = GDriveSearchEngine(
            cfg.tokens,
            include_shared_drives=cfg.include_shared_drives,
            corpora=cfg.corpora,  # type: ignore[arg-type]
        )
        accounts = _engine.resolve_accounts()
        return {"status": "ok", "token_count": len(cfg.tokens), "accounts": accounts}

    @router.get("/search/gdrive")
    def gdrive_search(
        q: str = FQuery("", description="Drive query string or plain keyword"),
        kind: SearchKind = FQuery("files"),
        order_by: str = FQuery("modifiedTime desc"),
        limit: int = FQuery(20, ge=1, le=1000),
        page_token: Optional[str] = FQuery(None),
        drive_id: Optional[str] = FQuery(None),
        x_gdrive_token: str | None = Header(default=None, alias="X-GDrive-Token"),
    ):
        engine = _engine
        if x_gdrive_token:
            engine = GDriveSearchEngine([x_gdrive_token])
        if engine is None:
            env_tokens = _env_tokens()
            if env_tokens:
                engine = GDriveSearchEngine(env_tokens)
        if engine is None:
            raise HTTPException(422, "No tokens configured. Set GDRIVE_TOKEN or POST /search/gdrive/configure.")
        try:
            return engine.search(q, kind, order_by=order_by, limit=limit,
                                 page_token=page_token, drive_id=drive_id).to_dict()
        except RateLimitError as e:
            raise HTTPException(429, str(e))
        except AuthError as e:
            raise HTTPException(401, str(e))
        except ScopeError as e:
            raise HTTPException(403, str(e))
        except SearchSyntaxError as e:
            raise HTTPException(400, str(e))
        except GDriveSearchError as e:
            raise HTTPException(502, str(e))

    @router.get("/search/gdrive/tokens/status")
    def token_status():
        engine = _ensure_engine()
        if engine is None:
            raise HTTPException(422, "No tokens configured.")
        _refresh_if_needed(engine)
        return engine.token_status

    @router.get("/search/gdrive/accounts")
    def accounts():
        engine = _ensure_engine()
        if engine is None:
            raise HTTPException(422, "No tokens configured.")
        return engine.resolve_accounts()

except ImportError:
    pass


# ── CLI / quick demo ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys, os

    token = os.getenv("GDRIVE_TOKEN") or (sys.argv[1] if len(sys.argv) > 1 else None)
    query = sys.argv[2] if len(sys.argv) > 2 else "invoice"
    kind  = sys.argv[3] if len(sys.argv) > 3 else "files"

    if not token:
        print("Usage: python gdrive_search.py <access_token> [query] [kind]")
        print("   or: GDRIVE_TOKEN=ya29... python gdrive_search.py")
        print()
        print("Token kinds: files · folders · shared_drives · comments · revisions")
        sys.exit(1)

    engine = GDriveSearchEngine(tokens=[token])

    print("\n🔍 Checking account…")
    for acc in engine.resolve_accounts():
        print(f"  ✅ {acc.get('email', '?')}  ({acc.get('domain', '?')})")

    print(f"\n🔍 Searching Drive [{kind}]: {query!r}\n")
    resp = engine.search(query, kind=kind, limit=5)  # type: ignore[arg-type]
    print(f"  {resp.total_count} results  ·  {resp.elapsed_ms}ms\n")

    for item in resp.items:
        d = vars(item)
        if kind == "files":
            size_kb = d.get("size", 0) // 1024
            print(f"  [{d.get('kind','?')}] {d.get('name', '')}")
            print(f"    owners: {', '.join(d.get('owners', []))}  ·  {size_kb}KB")
            print(f"    {d.get('web_view_link', '')}")
        elif kind == "folders":
            print(f"  📁 {d.get('name', '')}")
            print(f"    owners: {', '.join(d.get('owners', []))}  ·  {d.get('modified_time', '')[:10]}")
            print(f"    {d.get('web_view_link', '')}")
        elif kind == "shared_drives":
            print(f"  🗂️  {d.get('name', '')}  (id: {d.get('id', '')})")
        elif kind == "comments":
            print(f"  💬 [{d.get('file_name','')}]  {d.get('author','')}: {d.get('content','')[:80]}")
        elif kind == "revisions":
            print(f"  📝 {d.get('file_name','')}  rev:{d.get('id','')}  by {d.get('last_modifying_user','')}")
            print(f"    {d.get('modified_time','')[:10]}")
        print()
