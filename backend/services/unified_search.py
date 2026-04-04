"""
unified_search.py
-----------------
Combines GitHub (authenticated user repos + file metadata), Slack, and Google Drive
search into a single /search/unified endpoint consumed by the frontend.

GitHub search now works in two modes:
  1. User-repo search (default): fetches the authenticated user's repos via
     /user/repos, filters by query, and searches each repo's file tree for
     matching filenames/paths. This is how personal repos like 'clawtech' get found.

  2. Public code search (fallback when no token): uses GitHub's public /search
     API to search code, repos, issues, commits, or users.
"""

from __future__ import annotations

import asyncio
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Header, Query

from services.github_search import GitHubSearchEngine, AuthError as GhAuthError, GitHubSearchError
from services.slack_search import SlackSearchEngine, AuthError as SlackAuthError, SlackSearchError
from services.gdrive_search import GDriveSearchEngine, AuthError as GdAuthError, GDriveSearchError


router = APIRouter(tags=["Unified Search"])

GITHUB_API = "https://api.github.com"


# ── Token helpers ─────────────────────────────────────────────────────────────

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


def _get_github_token(x_token: Optional[str]) -> Optional[str]:
    """Return a raw token string for use with httpx calls."""
    if x_token:
        return x_token
    env = os.getenv("GITHUB_TOKENS") or ""
    if env.strip():
        return _split_tokens(env)[0]
    return os.getenv("GITHUB_TOKEN")


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


# ── GitHub authenticated user-repo search ────────────────────────────────────

def _gh_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }


async def _fetch_all_user_repos(token: str, owner: Optional[str] = None) -> list[dict]:
    """
    Fetch every repo the authenticated user has access to (raw GitHub dicts).
    Returns up to 100 repos sorted by recently-updated, no query filtering.
    """
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{GITHUB_API}/user/repos",
            headers=_gh_headers(token),
            params={
                "per_page": 100,
                "affiliation": "owner",
                "sort": "updated",
            },
        )
        resp.raise_for_status()
        repos = resp.json()
        if owner:
            repos = [r for r in repos if (r.get("owner") or {}).get("login", "").lower() == owner.lower()]
        return repos


def _match_repos(raw_repos: list[dict], query: str, limit: int) -> list[dict]:
    """
    Filter raw repo dicts by name / full_name / description / topics.
    Returns unified-search-formatted dicts for repo-level hits only.
    """
    q = query.lower()
    results: list[dict] = []

    for r in raw_repos:
        name: str = r.get("name", "")
        full_name: str = r.get("full_name", "")
        desc: str = r.get("description") or ""
        topics: list[str] = r.get("topics") or []

        if not (
            q in name.lower()
            or q in full_name.lower()
            or q in desc.lower()
            or any(q in t.lower() for t in topics)
        ):
            continue

        results.append({
            "source": "github",
            "kind": "repositories",
            "title": full_name,
            "snippet": desc or f"⭐ {r.get('stargazers_count', 0)}  {r.get('language') or 'No language'}",
            "url": r.get("html_url", ""),
            "meta": {
                "repo": full_name,
                "language": r.get("language"),
                "stars": r.get("stargazers_count", 0),
                "private": r.get("private", False),
            },
            "score": 1.0,
        })

        if len(results) >= limit:
            break

    return results


async def _fetch_repo_files(token: str, full_name: str, query: str, limit: int) -> list[dict]:
    """
    Walk a single repo's git tree (metadata only — no file content accessed).
    Matches files and folders whose name, path segment, or extension contains the query.
    """
    q = query.lower()
    results: list[dict] = []

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(
                f"{GITHUB_API}/repos/{full_name}/git/trees/HEAD",
                headers=_gh_headers(token),
                params={"recursive": "1"},
            )
            if resp.status_code == 409:
                return []          # empty repo — no commits yet
            resp.raise_for_status()
            tree: list[dict] = resp.json().get("tree", [])
        except Exception as exc:
            print(f"[search] tree fetch failed for {full_name}: {exc}")
            return []

    repo_url = f"https://github.com/{full_name}"

    for item in tree:
        item_type = item.get("type")   # "blob" = file, "tree" = directory
        if item_type not in ("blob", "tree"):
            continue

        path: str = item.get("path", "")
        name: str = path.split("/")[-1] if path else ""
        ext_parts = name.rsplit(".", 1)
        extension: str = ext_parts[1].lower() if len(ext_parts) == 2 else ""

        # Match if query appears in any path segment or extension
        path_segments = [seg.lower() for seg in path.split("/")]
        matched = (
            q in name.lower()
            or any(q in seg for seg in path_segments)
            or (extension and q in extension)
        )
        if not matched:
            continue

        # Directories link to tree view; files to blob view
        if item_type == "tree":
            url = f"{repo_url}/tree/HEAD/{path}"
        else:
            url = f"{repo_url}/blob/HEAD/{path}"

        # Score tiers
        if name.lower() == q:
            score = 1.0
        elif q in name.lower():
            score = 0.85
        else:
            score = 0.7

        results.append({
            "source": "github",
            "kind": "file_metadata",
            "title": name,
            "snippet": f"{full_name}  ›  {path}",
            "url": url,
            "meta": {
                "repo": full_name,
                "path": path,
                "extension": extension if extension and extension != name else None,
                "size": item.get("size"),    # None for directories
                "type": "dir" if item_type == "tree" else "file",
            },
            "score": score,
        })

    # Sort: exact name matches first → score desc → shallower paths first
    results.sort(key=lambda r: (
        0 if r["title"].lower() == q else 1,
        -r["score"],
        r["meta"]["path"].count("/"),
    ))
    return results[:limit]


async def _github_user_search(
    token: str,
    query: str,
    per_source: int,
    *,
    owner: Optional[str] = None,
    repo_full_name: Optional[str] = None,
) -> tuple[list[dict], list[dict]]:
    """
    Two-phase search (metadata only — no file content is read):

    Phase 1 — Repo-level:
        Filter repos whose name / description / topics match the query.

    Phase 2 — File-metadata:
        Scan ALL repos' git trees for files/folders whose name or path
        contains the query. Scans up to 15 most-recently-updated repos
        concurrently to stay within GitHub rate limits.
    """
    errors: list[dict] = []
    results: list[dict] = []

    try:
        # Single API call to get all repos
        raw_repos = await _fetch_all_user_repos(token, owner=owner)
        if repo_full_name:
            raw_repos = [r for r in raw_repos if (r.get("full_name") or "").lower() == repo_full_name.lower()]

        # Phase 1: repo-level matches (no extra API calls)
        repo_results = _match_repos(raw_repos, query, limit=per_source)
        results.extend(repo_results)

        # Phase 2: file-metadata scan across ALL repos concurrently
        repos_to_scan = [r.get("full_name", "") for r in raw_repos[:15] if r.get("full_name")]

        file_tasks = [
            _fetch_repo_files(token, repo_name, query, limit=per_source)
            for repo_name in repos_to_scan
        ]
        file_result_groups = await asyncio.gather(*file_tasks, return_exceptions=True)

        seen: set[str] = set()
        for group in file_result_groups:
            if not isinstance(group, list):
                continue
            for item in group:
                key = f"{item['meta']['repo']}:{item['meta']['path']}"
                if key not in seen:
                    seen.add(key)
                    results.append(item)

    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if code in (401, 403):
            errors.append({"source": "github", "error": "Authentication failed — check GITHUB_TOKEN."})
        else:
            errors.append({"source": "github", "error": f"GitHub API error: {code}"})
    except Exception as exc:
        errors.append({"source": "github", "error": str(exc)})

    return results, errors


# ── Mapper for old public GitHub search engine (fallback) ────────────────────


def _map_github_item(kind: str, item: dict) -> dict:
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
    if kind == "commits":
        return {
            "title": item.get("message"),
            "snippet": item.get("author"),
            "url": item.get("url"),
            "meta": {"repo": item.get("repo"), "sha": item.get("sha")},
            "score": item.get("score", 0.0),
        }
    if kind == "users":
        return {
            "title": item.get("login"),
            "snippet": item.get("name") or item.get("bio", ""),
            "url": item.get("url"),
            "meta": {"followers": item.get("followers"), "repos": item.get("public_repos")},
            "score": item.get("score", 0.0),
        }
    return {"title": item.get("name", ""), "snippet": "", "url": "", "meta": {}, "score": 0.0}


def _map_slack_item(kind: str, item: dict) -> dict:
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
    if kind == "channels":
        return {
            "title": f"#{item.get('name','')}",
            "snippet": item.get("purpose", ""),
            "url": "",
            "meta": {"members": item.get("member_count"), "private": item.get("is_private")},
            "score": 0.0,
        }
    if kind == "users":
        return {
            "title": f"@{item.get('name','')}",
            "snippet": item.get("title") or item.get("real_name", ""),
            "url": "",
            "meta": {"email": item.get("email"), "team": item.get("team_id")},
            "score": 0.0,
        }
    return {"title": item.get("name", ""), "snippet": "", "url": "", "meta": {}, "score": 0.0}


def _map_gdrive_item(kind: str, item: dict) -> dict:
    if kind in ("files", "folders"):
        return {
            "title": item.get("name"),
            "snippet": item.get("full_text_snippet") or item.get("description", ""),
            "url": item.get("web_view_link"),
            "meta": {"mime": item.get("mime_type"), "owners": item.get("owners")},
            "score": 0.0,
        }
    if kind == "shared_drives":
        return {
            "title": item.get("name"),
            "snippet": "Shared drive",
            "url": "",
            "meta": {"id": item.get("id")},
            "score": 0.0,
        }
    if kind == "comments":
        return {
            "title": item.get("file_name"),
            "snippet": item.get("content", ""),
            "url": "",
            "meta": {"author": item.get("author"), "file_id": item.get("file_id")},
            "score": 0.0,
        }
    if kind == "revisions":
        return {
            "title": item.get("file_name"),
            "snippet": item.get("last_modifying_user", ""),
            "url": "",
            "meta": {"revision": item.get("id"), "file_id": item.get("file_id")},
            "score": 0.0,
        }
    return {"title": item.get("name", ""), "snippet": "", "url": "", "meta": {}, "score": 0.0}


# ── Main endpoint ─────────────────────────────────────────────────────────────

@router.get("/search/unified")
async def unified_search(
    q: str = Query(..., description="Unified query string"),
    sources: str = Query("github,slack,gdrive", description="Comma-separated sources"),
    per_source: int = Query(10, ge=1, le=50),
    github_kind: str = Query("repositories", description="Used only when no GitHub token (public search fallback)"),
    github_repo: str | None = Query(None, description="GitHub repo scope for public search: owner/name"),
    github_owner: str | None = Query(None, description="GitHub owner scope"),
    slack_kind: str = Query("messages"),
    gdrive_kind: str = Query("files"),
    x_github_token: str | None = Header(default=None, alias="X-GitHub-Token"),
    x_slack_token: str | None = Header(default=None, alias="X-Slack-Token"),
    x_gdrive_token: str | None = Header(default=None, alias="X-GDrive-Token"),
):
    selected = {s.strip() for s in sources.split(",") if s.strip()}
    results: list[dict] = []
    errors: list[dict] = []

    # ── GitHub ────────────────────────────────────────────────────────────────
    if "github" in selected:
        token = _get_github_token(x_github_token)
        if token:
            # Authenticated path: search user's own repos + file metadata
            gh_results, gh_errors = await _github_user_search(
                token,
                q,
                per_source,
                owner=github_owner,
                repo_full_name=github_repo,
            )
            results.extend(gh_results)
            errors.extend(gh_errors)
        else:
            # Fallback: public GitHub search API
            engine = _github_engine(x_github_token)
            if not engine:
                errors.append({"source": "github", "error": "Missing GitHub token"})
            else:
                try:
                    gh_query = q
                    if github_repo and github_kind in {"code", "issues", "commits"}:
                        gh_query = f"repo:{github_repo} {q}"
                    elif github_owner and github_kind in {"code", "issues", "commits"}:
                        gh_query = f"user:{github_owner} {q}"
                    resp = engine.search(gh_query, kind=github_kind, limit=per_source).to_dict()
                    items = resp.get("items", [])
                    if github_repo and github_kind == "repositories":
                        items = [i for i in items if i.get("full_name") == github_repo]
                    if github_owner and github_kind == "repositories":
                        items = [i for i in items if (i.get("full_name") or "").lower().startswith(f"{github_owner.lower()}/")]
                    for item in items:
                        results.append({
                            "source": "github",
                            "kind": github_kind,
                            **_map_github_item(github_kind, item),
                        })
                except (GhAuthError, GitHubSearchError) as e:
                    errors.append({"source": "github", "error": str(e)})

    # ── Slack ─────────────────────────────────────────────────────────────────
    if "slack" in selected:
        engine = _slack_engine(x_slack_token)
        if not engine:
            demo_items = [
                {
                    "channel_name": "announcements",
                    "username": "ops-team",
                    "text": f"Release note: {q} indexed in the knowledge graph.",
                    "permalink": "",
                    "team": "demo",
                    "timestamp": "demo",
                    "score": 0.0,
                },
                {
                    "channel_name": "engineering",
                    "username": "build-bot",
                    "text": "Build pipeline synchronized with GitHub repo updates.",
                    "permalink": "",
                    "team": "demo",
                    "timestamp": "demo",
                    "score": 0.0,
                },
            ]
            for item in demo_items[:per_source]:
                results.append({
                    "source": "slack",
                    "kind": "demo",
                    "meta": {"demo": True},
                    **_map_slack_item("messages", item),
                })
        else:
            try:
                resp = engine.search(q, kind=slack_kind, limit=per_source).to_dict()
                for item in resp.get("items", []):
                    results.append({
                        "source": "slack",
                        "kind": slack_kind,
                        **_map_slack_item(slack_kind, item),
                    })
            except (SlackAuthError, SlackSearchError) as e:
                errors.append({"source": "slack", "error": str(e)})

    # ── Google Drive ──────────────────────────────────────────────────────────
    if "gdrive" in selected:
        engine = _gdrive_engine(x_gdrive_token)
        if not engine:
            errors.append({"source": "gdrive", "error": "Missing Google Drive token"})
        else:
            try:
                resp = engine.search(q, kind=gdrive_kind, limit=per_source).to_dict()
                for item in resp.get("items", []):
                    results.append({
                        "source": "gdrive",
                        "kind": gdrive_kind,
                        **_map_gdrive_item(gdrive_kind, item),
                    })
            except (GdAuthError, GDriveSearchError) as e:
                errors.append({"source": "gdrive", "error": str(e)})

    return {"query": q, "count": len(results), "results": results, "errors": errors}
