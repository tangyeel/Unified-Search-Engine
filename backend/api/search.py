"""
backend/api/search.py
Ported from server/router/search.ts

Exposes:
  POST /search/repositories  – search authenticated user's repos (uses GITHUB_TOKEN from .env)
  GET  /search/public        – search a public owner's repos (no auth required)
"""

from __future__ import annotations

import os
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/search", tags=["Search"])

GITHUB_API = "https://api.github.com"


# ── Pydantic models ──────────────────────────────────────────────────────────

class GitHubRepo(BaseModel):
    id: int
    name: str
    full_name: str
    description: Optional[str] = None
    url: str
    html_url: str
    language: Optional[str] = None
    stargazers_count: int = 0
    forks_count: int = 0
    open_issues_count: int = 0
    topics: list[str] = []
    updated_at: str = ""


class FileMetadata(BaseModel):
    path: str
    name: str
    type: str  # "file" | "dir"
    size: Optional[int] = None
    repo: str
    repoUrl: str
    url: str
    extension: Optional[str] = None


class ContentMatch(BaseModel):
    path: str
    repo: str
    snippet: str
    url: str


class SearchResult(BaseModel):
    repositories: list[GitHubRepo] = []
    content: list[ContentMatch] = []
    files: list[FileMetadata] = []
    total: int = 0


class RepositorySearchRequest(BaseModel):
    query: str


# ── Helpers ──────────────────────────────────────────────────────────────────

def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }


def _get_token() -> str:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="GitHub token not configured")
    return token


async def _search_user_repos(token: str, query: str) -> list[GitHubRepo]:
    """Fetch all repos the authenticated user has access to, filtered by query."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{GITHUB_API}/user/repos",
            headers=_headers(token),
            params={
                "per_page": 100,
                "affiliation": "owner,collaborator,organization_member",
            },
        )
        resp.raise_for_status()
        raw: list[dict] = resp.json()

    q = query.lower()
    results: list[GitHubRepo] = []
    for r in raw:
        if (
            q in r.get("name", "").lower()
            or q in r.get("full_name", "").lower()
            or q in (r.get("description") or "").lower()
            or any(q in t.lower() for t in (r.get("topics") or []))
        ):
            results.append(GitHubRepo(
                id=r["id"],
                name=r["name"],
                full_name=r["full_name"],
                description=r.get("description"),
                url=r.get("url", ""),
                html_url=r.get("html_url", ""),
                language=r.get("language"),
                stargazers_count=r.get("stargazers_count", 0),
                forks_count=r.get("forks_count", 0),
                open_issues_count=r.get("open_issues_count", 0),
                topics=r.get("topics") or [],
                updated_at=r.get("updated_at", ""),
            ))
    return results


async def _search_repo_content(
    token: str, repos: list[GitHubRepo], query: str
) -> list[ContentMatch]:
    """Search code inside the first 5 repos to stay within rate limits."""
    results: list[ContentMatch] = []
    content_headers = {
        **_headers(token),
        "Accept": "application/vnd.github+json,application/vnd.github.text-match+json",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        for repo in repos[:5]:
            try:
                resp = await client.get(
                    f"{GITHUB_API}/search/code",
                    headers=content_headers,
                    params={"q": f"repo:{repo.full_name} {query}", "per_page": 10},
                )
                resp.raise_for_status()
                for item in resp.json().get("items", []):
                    snippet = ""
                    matches = item.get("text_matches") or []
                    if matches:
                        snippet = matches[0].get("fragment", "")
                    results.append(ContentMatch(
                        path=item.get("path", ""),
                        repo=repo.full_name,
                        snippet=snippet,
                        url=item.get("html_url", ""),
                    ))
            except Exception as exc:  # noqa: BLE001
                print(f"[search] code search failed for {repo.full_name}: {exc}")
    return results


async def _search_file_metadata(
    token: str, repos: list[GitHubRepo], query: str
) -> list[FileMetadata]:
    """Walk the git tree of the first 10 repos and match files by name/path/extension."""
    results: list[FileMetadata] = []
    q = query.lower()

    async with httpx.AsyncClient(timeout=10) as client:
        for repo in repos[:10]:
            try:
                resp = await client.get(
                    f"{GITHUB_API}/repos/{repo.full_name}/git/trees/HEAD",
                    headers=_headers(token),
                    params={"recursive": "1"},
                )
                resp.raise_for_status()
                tree = resp.json().get("tree", [])

                for item in tree:
                    path: str = item.get("path", "")
                    name: str = path.split("/")[-1] if path else ""
                    ext_parts = name.rsplit(".", 1)
                    extension: Optional[str] = ext_parts[1] if len(ext_parts) == 2 else None

                    if (
                        q in path.lower()
                        or q in name.lower()
                        or (extension and q in extension.lower())
                    ):
                        results.append(FileMetadata(
                            path=path,
                            name=name,
                            type="file" if item.get("type") == "blob" else "dir",
                            size=item.get("size"),
                            repo=repo.full_name,
                            repoUrl=repo.html_url,
                            url=f"{repo.html_url}/blob/HEAD/{path}",
                            extension=extension,
                        ))
            except Exception as exc:  # noqa: BLE001
                print(f"[search] tree fetch failed for {repo.full_name}: {exc}")

    # Sort: exact name matches first, then by path length (shorter = more relevant)
    results.sort(key=lambda f: (0 if f.name.lower() == q else 1, len(f.path)))
    return results


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("/repositories", response_model=SearchResult, summary="Search authenticated user's GitHub repos")
async def search_repositories(body: RepositorySearchRequest) -> SearchResult:
    """
    Search across all repositories the authenticated user has access to.
    Mirrors the `searchRouter.repositories` tRPC mutation.
    Token is read from GITHUB_TOKEN in .env.
    """
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    token = _get_token()

    repositories = await _search_user_repos(token, body.query)
    content = await _search_repo_content(token, repositories, body.query)
    files = await _search_file_metadata(token, repositories, body.query)

    return SearchResult(
        repositories=repositories,
        content=content,
        files=files,
        total=len(repositories) + len(content) + len(files),
    )


@router.get("/public", response_model=SearchResult, summary="Search a public GitHub owner's repos")
async def public_search(
    query: str = Query(..., description="Search keyword"),
    owner: Optional[str] = Query(None, description="GitHub username/org to scope the search"),
) -> SearchResult:
    """
    Public search endpoint — no user auth required.
    Mirrors the `searchRouter.publicSearch` tRPC query.
    If `owner` is provided, searches that user's public repos.
    """
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    if not owner:
        raise HTTPException(status_code=400, detail="owner parameter is required for public search")

    token = _get_token()

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{GITHUB_API}/users/{owner}/repos",
            headers={"Accept": "application/vnd.github+json"},
            params={"per_page": 100, "sort": "updated"},
        )
        resp.raise_for_status()
        raw: list[dict] = resp.json()

    q = query.lower()
    filtered: list[GitHubRepo] = []
    for r in raw:
        if (
            q in r.get("name", "").lower()
            or q in r.get("full_name", "").lower()
            or q in (r.get("description") or "").lower()
        ):
            filtered.append(GitHubRepo(
                id=r["id"],
                name=r["name"],
                full_name=r["full_name"],
                description=r.get("description"),
                url=r.get("url", ""),
                html_url=r.get("html_url", ""),
                language=r.get("language"),
                stargazers_count=r.get("stargazers_count", 0),
                forks_count=r.get("forks_count", 0),
                open_issues_count=r.get("open_issues_count", 0),
                topics=r.get("topics") or [],
                updated_at=r.get("updated_at", ""),
            ))

    files = await _search_file_metadata(token, filtered, query)

    return SearchResult(
        repositories=filtered,
        content=[],
        files=files,
        total=len(filtered) + len(files),
    )
