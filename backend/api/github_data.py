"""
api/github_data.py
------------------
Async endpoints that power the Mind Map and Dashboard pages with real GitHub data.

  GET /github/me           – authenticated user profile + repo summary
  GET /github/repos/tree   – file/folder tree for a single repo (mind map nodes)
  GET /github/dashboard    – user stats: profile, repos, recent commits, languages
"""

from __future__ import annotations

import asyncio
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Header, Query

router = APIRouter(tags=["GitHub Data"])

GITHUB_API = "https://api.github.com"


def _token() -> Optional[str]:
    return os.getenv("GITHUB_TOKEN")


def _hdrs(tok: str) -> dict:
    return {
        "Authorization": f"Bearer {tok}",
        "Accept": "application/vnd.github+json",
    }


# ── /github/repos/list ───────────────────────────────────────────────────────

@router.get("/github/repos/list")
async def list_repos_for_mindmap(
    x_github_token: Optional[str] = Header(default=None, alias="X-GitHub-Token"),
):
    """Return all user repos as lightweight mind-map nodes."""
    tok = x_github_token or _token()
    if not tok:
        return {"error": "No GitHub token configured.", "repos": []}

    async with httpx.AsyncClient(timeout=12) as client:
        resp = await client.get(
            f"{GITHUB_API}/user/repos",
            headers=_hdrs(tok),
            params={"per_page": 100, "sort": "updated", "affiliation": "owner,collaborator,organization_member"},
        )
        if resp.status_code != 200:
            return {"error": f"GitHub {resp.status_code}", "repos": []}
        raw = resp.json()

    repos = [
        {
            "id": r["id"],
            "name": r["name"],
            "full_name": r["full_name"],
            "private": r.get("private", False),
            "language": r.get("language"),
            "description": r.get("description") or "",
            "stars": r.get("stargazers_count", 0),
            "forks": r.get("forks_count", 0),
            "html_url": r.get("html_url", ""),
            "updated_at": r.get("updated_at", ""),
            "default_branch": r.get("default_branch", "main"),
        }
        for r in raw
    ]
    return {"repos": repos}


# ── /github/repos/tree ───────────────────────────────────────────────────────

@router.get("/github/repos/tree")
async def repo_tree(
    full_name: str = Query(..., description="owner/repo"),
    x_github_token: Optional[str] = Header(default=None, alias="X-GitHub-Token"),
):
    """
    Return the top-level file tree of a repo as mind-map child nodes.
    Only returns depth-1 entries (immediate children of root) to keep it fast.
    """
    tok = x_github_token or _token()
    if not tok:
        return {"error": "No GitHub token", "nodes": []}

    async with httpx.AsyncClient(timeout=12) as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{full_name}/git/trees/HEAD",
            headers=_hdrs(tok),
            params={"recursive": "0"},   # depth-1 only
        )
        if resp.status_code == 409:
            return {"nodes": []}          # empty repo
        if resp.status_code != 200:
            return {"error": f"GitHub {resp.status_code}", "nodes": []}
        tree = resp.json().get("tree", [])

    nodes = [
        {
            "path": item["path"],
            "type": "dir" if item["type"] == "tree" else "file",
            "size": item.get("size"),
            "sha": item.get("sha", ""),
        }
        for item in tree
        if item.get("type") in ("blob", "tree")
    ]
    # Dirs first, then files, both alphabetically
    nodes.sort(key=lambda n: (0 if n["type"] == "dir" else 1, n["path"].lower()))
    return {"repo": full_name, "nodes": nodes}


# ── /github/dashboard ────────────────────────────────────────────────────────

@router.get("/github/dashboard")
async def dashboard(
    x_github_token: Optional[str] = Header(default=None, alias="X-GitHub-Token"),
):
    """
    Aggregate real GitHub data for the dashboard:
      - Authenticated user profile
      - All repos (stats)
      - Per-language breakdown
      - Recent commits across 5 most-updated repos
    """
    tok = x_github_token or _token()
    if not tok:
        return {"error": "No GitHub token configured."}

    async with httpx.AsyncClient(timeout=15) as client:

        # 1. User profile
        user_resp = await client.get(f"{GITHUB_API}/user", headers=_hdrs(tok))
        user = user_resp.json() if user_resp.status_code == 200 else {}

        # 2. All repos
        repos_resp = await client.get(
            f"{GITHUB_API}/user/repos",
            headers=_hdrs(tok),
            params={"per_page": 100, "sort": "updated", "affiliation": "owner,collaborator,organization_member"},
        )
        raw_repos = repos_resp.json() if repos_resp.status_code == 200 else []

        # 3. Recent commits – fire off requests for top 5 repos concurrently
        top5 = [r["full_name"] for r in raw_repos[:5] if r.get("full_name")]

        async def _commits(full_name: str):
            r = await client.get(
                f"{GITHUB_API}/repos/{full_name}/commits",
                headers=_hdrs(tok),
                params={"per_page": 5},
            )
            if r.status_code != 200:
                return []
            return [
                {
                    "repo": full_name,
                    "sha": c["sha"][:7],
                    "message": (c.get("commit", {}).get("message") or "").split("\n")[0][:80],
                    "author": (c.get("commit", {}).get("author") or {}).get("name", ""),
                    "date": (c.get("commit", {}).get("author") or {}).get("date", ""),
                    "url": c.get("html_url", ""),
                }
                for c in r.json()
                if isinstance(c, dict)
            ]

        commit_groups = await asyncio.gather(*[_commits(fn) for fn in top5], return_exceptions=True)

    # Flatten commits, sort newest first
    all_commits = []
    for g in commit_groups:
        if isinstance(g, list):
            all_commits.extend(g)
    all_commits.sort(key=lambda c: c.get("date", ""), reverse=True)
    recent_commits = all_commits[:15]

    # Language breakdown
    lang_counts: dict[str, int] = {}
    for r in raw_repos:
        lang = r.get("language")
        if lang:
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
    top_langs = sorted(lang_counts.items(), key=lambda x: -x[1])[:6]

    # Repo summaries
    repos_summary = [
        {
            "name": r.get("name"),
            "full_name": r.get("full_name"),
            "description": r.get("description") or "",
            "language": r.get("language"),
            "stars": r.get("stargazers_count", 0),
            "forks": r.get("forks_count", 0),
            "open_issues": r.get("open_issues_count", 0),
            "private": r.get("private", False),
            "html_url": r.get("html_url", ""),
            "updated_at": r.get("updated_at", ""),
        }
        for r in raw_repos[:20]
    ]

    return {
        "user": {
            "login": user.get("login", ""),
            "name": user.get("name") or user.get("login", ""),
            "avatar_url": user.get("avatar_url", ""),
            "bio": user.get("bio") or "",
            "public_repos": user.get("public_repos", 0),
            "followers": user.get("followers", 0),
            "following": user.get("following", 0),
            "html_url": user.get("html_url", ""),
        },
        "stats": {
            "total_repos": len(raw_repos),
            "total_stars": sum(r.get("stargazers_count", 0) for r in raw_repos),
            "total_forks": sum(r.get("forks_count", 0) for r in raw_repos),
            "total_open_issues": sum(r.get("open_issues_count", 0) for r in raw_repos),
            "private_repos": sum(1 for r in raw_repos if r.get("private")),
        },
        "languages": [{"name": l, "count": c} for l, c in top_langs],
        "repos": repos_summary,
        "recent_commits": recent_commits,
    }
