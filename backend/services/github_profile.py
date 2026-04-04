from __future__ import annotations

import os
from typing import Optional

import requests
from fastapi import APIRouter, Header, HTTPException, Query

from services.http_client import build_session

GITHUB_API = "https://api.github.com"

router = APIRouter(prefix="/github", tags=["GitHub"])

_SESSION = build_session()


def _headers(token: Optional[str]) -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _token_from_env_or_header(x_github_token: Optional[str]) -> Optional[str]:
    return x_github_token or os.getenv("GITHUB_TOKEN")


def _authed_user(token: str) -> Optional[dict]:
    try:
        resp = _SESSION.get(f"{GITHUB_API}/user", headers=_headers(token), timeout=8)
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        return None
    return None


def _public_user(login: str) -> Optional[dict]:
    try:
        resp = _SESSION.get(f"{GITHUB_API}/users/{login}", headers=_headers(None), timeout=8)
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        return None
    return None


@router.get("/dashboard")
def github_dashboard(
    user: Optional[str] = Query(None, description="GitHub username (optional)"),
    x_github_token: Optional[str] = Header(default=None, alias="X-GitHub-Token"),
):
    token = _token_from_env_or_header(x_github_token)
    authed = _authed_user(token) if token else None
    login = (authed or {}).get("login")

    if not token and not user:
        raise HTTPException(400, "Provide user or configure GITHUB_TOKEN.")

    profile = authed or (_public_user(user) if user else None)
    if not profile:
        raise HTTPException(404, "GitHub profile not found.")

    try:
        if token:
            repo_resp = _SESSION.get(
                f"{GITHUB_API}/user/repos",
                headers=_headers(token),
                params={"per_page": 100, "affiliation": "owner"},
                timeout=12,
            )
        else:
            repo_resp = _SESSION.get(
                f"{GITHUB_API}/users/{user}/repos",
                headers=_headers(None),
                params={"per_page": 100, "sort": "updated"},
                timeout=12,
            )
        if repo_resp.status_code != 200:
            raise HTTPException(repo_resp.status_code, repo_resp.json().get("message", "GitHub error"))

        repos = repo_resp.json()
    except HTTPException:
        raise
    except requests.RequestException as e:
        raise HTTPException(502, f"Network error: {e}")

    if user and login and user.lower() != login.lower():
        repos = [r for r in repos if (r.get("owner") or {}).get("login", "").lower() == user.lower()]

    stats = {
        "total_repos": len(repos),
        "total_stars": sum(r.get("stargazers_count", 0) for r in repos),
        "total_forks": sum(r.get("forks_count", 0) for r in repos),
        "private_repos": sum(1 for r in repos if r.get("private")),
    }

    lang_counts: dict[str, int] = {}
    for r in repos:
        lang = r.get("language") or "Unknown"
        lang_counts[lang] = lang_counts.get(lang, 0) + 1
    languages = [{"name": k, "count": v} for k, v in sorted(lang_counts.items(), key=lambda x: x[1], reverse=True)][:8]

    # Recent commits for top 5 repos by pushed_at
    repos_sorted = sorted(repos, key=lambda r: r.get("pushed_at") or "", reverse=True)[:5]
    commits: list[dict] = []
    for r in repos_sorted:
        owner_login = (r.get("owner") or {}).get("login")
        repo_name = r.get("name")
        if not owner_login or not repo_name:
            continue
        try:
            commit_resp = _SESSION.get(
                f"{GITHUB_API}/repos/{owner_login}/{repo_name}/commits",
                headers=_headers(token),
                params={"per_page": 3},
                timeout=10,
            )
            if commit_resp.status_code != 200:
                continue
            for c in commit_resp.json():
                commit_data = c.get("commit") or {}
                author_data = (commit_data.get("author") or {})
                commits.append(
                    {
                        "sha": (c.get("sha") or "")[:7],
                        "message": (commit_data.get("message") or "").split("\n")[0],
                        "author": author_data.get("name") or (c.get("author") or {}).get("login") or "unknown",
                        "date": author_data.get("date"),
                        "url": c.get("html_url"),
                        "repo": f"{owner_login}/{repo_name}",
                    }
                )
        except requests.RequestException:
            continue

    return {
        "user": {
            "login": profile.get("login"),
            "name": profile.get("name"),
            "avatar_url": profile.get("avatar_url"),
            "bio": profile.get("bio"),
            "followers": profile.get("followers"),
            "following": profile.get("following"),
            "public_repos": profile.get("public_repos"),
            "html_url": profile.get("html_url"),
        },
        "stats": stats,
        "languages": languages,
        "repos": [
            {
                "name": r.get("name"),
                "description": r.get("description"),
                "language": r.get("language"),
                "stars": r.get("stargazers_count", 0),
                "private": r.get("private", False),
                "updated_at": r.get("updated_at"),
                "html_url": r.get("html_url"),
            }
            for r in sorted(repos, key=lambda r: r.get("updated_at") or "", reverse=True)
        ],
        "recent_commits": commits[:10],
    }


@router.get("/repos")
def list_repos(
    user: Optional[str] = Query(None, description="GitHub username (optional)"),
    per_page: int = Query(100, ge=1, le=100),
    x_github_token: Optional[str] = Header(default=None, alias="X-GitHub-Token"),
):
    token = _token_from_env_or_header(x_github_token)
    authed = _authed_user(token) if token else None
    login = (authed or {}).get("login")

    try:
        if token:
            resp = _SESSION.get(
                f"{GITHUB_API}/user/repos",
                headers=_headers(token),
                params={"per_page": per_page, "affiliation": "owner,collaborator,organization_member"},
                timeout=10,
            )
            if resp.status_code != 200:
                raise HTTPException(resp.status_code, resp.json().get("message", "GitHub error"))
            repos = resp.json()
            if user and login and user.lower() != login.lower():
                repos = [r for r in repos if (r.get("owner") or {}).get("login", "").lower() == user.lower()]
            return {
                "status": "ok",
                "source": "github",
                "user": user or login,
                "repos": [
                    {
                        "name": r.get("name"),
                        "full_name": r.get("full_name"),
                        "private": r.get("private", False),
                        "owner": (r.get("owner") or {}).get("login"),
                        "default_branch": r.get("default_branch"),
                        "description": r.get("description"),
                        "stars": r.get("stargazers_count", 0),
                        "forks": r.get("forks_count", 0),
                        "open_issues": r.get("open_issues_count", 0),
                        "language": r.get("language"),
                        "updated_at": r.get("updated_at"),
                        "pushed_at": r.get("pushed_at"),
                        "html_url": r.get("html_url"),
                    }
                    for r in repos
                ],
            }

        if not user:
            raise HTTPException(400, "Provide user when no token is configured.")

        resp = _SESSION.get(
            f"{GITHUB_API}/users/{user}/repos",
            headers=_headers(None),
            params={"per_page": per_page, "sort": "updated"},
            timeout=10,
        )
        if resp.status_code != 200:
            raise HTTPException(resp.status_code, resp.json().get("message", "GitHub error"))
        repos = resp.json()
        return {
            "status": "ok",
            "source": "public",
            "user": user,
            "repos": [
                {
                    "name": r.get("name"),
                    "full_name": r.get("full_name"),
                    "private": r.get("private", False),
                    "owner": (r.get("owner") or {}).get("login"),
                    "default_branch": r.get("default_branch"),
                    "description": r.get("description"),
                    "stars": r.get("stargazers_count", 0),
                    "forks": r.get("forks_count", 0),
                    "open_issues": r.get("open_issues_count", 0),
                    "language": r.get("language"),
                    "updated_at": r.get("updated_at"),
                    "pushed_at": r.get("pushed_at"),
                    "html_url": r.get("html_url"),
                }
                for r in repos
            ],
        }
    except HTTPException:
        raise
    except requests.RequestException as e:
        raise HTTPException(502, f"Network error: {e}")


@router.get("/repos/list")
def list_repos_simple(
    user: Optional[str] = Query(None, description="GitHub username (optional)"),
    per_page: int = Query(100, ge=1, le=100),
    x_github_token: Optional[str] = Header(default=None, alias="X-GitHub-Token"),
):
    data = list_repos(user=user, per_page=per_page, x_github_token=x_github_token)
    return {"repos": data.get("repos", []), "source": data.get("source"), "user": data.get("user")}


@router.get("/repos/tree")
def repo_tree(
    full_name: str = Query(..., description="owner/repo"),
    x_github_token: Optional[str] = Header(default=None, alias="X-GitHub-Token"),
):
    token = _token_from_env_or_header(x_github_token)
    if "/" not in full_name:
        raise HTTPException(400, "full_name must be owner/repo")
    owner, repo = full_name.split("/", 1)
    from services.github import fetch_tree

    tree, meta = fetch_tree(owner, repo, token)
    nodes = [
        {"path": item.get("path"), "type": "dir" if item.get("type") == "tree" else "file"}
        for item in tree
        if item.get("path")
    ]
    return {"nodes": nodes, "meta": meta}
