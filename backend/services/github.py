import os
import requests
from typing import Optional

from services.http_client import build_session

GITHUB_API = "https://api.github.com"

# ── Dummy fallback data (used when GitHub is unreachable / no token) ─────────

DUMMY_REPO = {
    "name": "payment-api",
    "full_name": "acme/payment-api",
    "description": "Stripe-based payment processing microservice",
    "language": "Python",
    "stargazers_count": 42,
    "open_issues_count": 5,
    "owner": {"login": "acme"},
}

DUMMY_CONTRIBUTORS = [
    {"login": "aditya", "contributions": 87},
    {"login": "priya", "contributions": 54},
    {"login": "rahul", "contributions": 23},
]

DUMMY_ISSUES = [
    {"number": 1, "title": "Login bug on mobile", "state": "open",
     "user": {"login": "priya"}, "body": "OAuth flow breaks on iOS Safari"},
    {"number": 2, "title": "Payment timeout error", "state": "open",
     "user": {"login": "aditya"}, "body": "Stripe webhook times out after 30 s"},
    {"number": 3, "title": "Refactor auth module", "state": "closed",
     "user": {"login": "rahul"}, "body": "Move JWT logic to dedicated service"},
]


def _headers(token: Optional[str]) -> dict:
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _effective_token(token: Optional[str]) -> Optional[str]:
    return token or os.getenv("GITHUB_TOKEN")


_SESSION = build_session()


def fetch_repo(owner: str, repo: str, token: Optional[str] = None) -> dict:
    url = f"{GITHUB_API}/repos/{owner}/{repo}"
    try:
        r = _SESSION.get(url, headers=_headers(_effective_token(token)), timeout=8)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"⚠️  GitHub repo fetch failed: {e}")
    # Fall back to dummy data
    dummy = dict(DUMMY_REPO)
    dummy["name"] = repo
    dummy["full_name"] = f"{owner}/{repo}"
    dummy["owner"] = {"login": owner}
    dummy["__fallback__"] = True
    return dummy


def fetch_contributors(owner: str, repo: str, token: Optional[str] = None) -> list:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contributors"
    try:
        r = _SESSION.get(url, headers=_headers(_effective_token(token)), timeout=8)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"⚠️  GitHub contributors fetch failed: {e}")
    return DUMMY_CONTRIBUTORS


def fetch_issues(owner: str, repo: str, token: Optional[str] = None) -> list:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/issues?state=all&per_page=20"
    try:
        r = _SESSION.get(url, headers=_headers(_effective_token(token)), timeout=8)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"⚠️  GitHub issues fetch failed: {e}")
    return DUMMY_ISSUES


def fetch_tree(owner: str, repo: str, token: Optional[str] = None, ref: Optional[str] = None) -> tuple[list, dict]:
    repo_info = fetch_repo(owner, repo, token)
    default_branch = ref or repo_info.get("default_branch", "main")
    meta = {
        "default_branch": default_branch,
        "tree_sha": None,
        "truncated": False,
        "tree_status": None,
        "ref_status": None,
        "tree_url": None,
    }

    headers = _headers(_effective_token(token))

    # Resolve branch -> sha
    ref_url = f"{GITHUB_API}/repos/{owner}/{repo}/git/refs/heads/{default_branch}"
    try:
        ref_res = _SESSION.get(ref_url, headers=headers, timeout=8)
        meta["ref_status"] = ref_res.status_code
        if ref_res.status_code == 200:
            ref_data = ref_res.json()
            meta["tree_sha"] = (ref_data.get("object") or {}).get("sha")
    except Exception as e:
        print(f"⚠️  GitHub ref fetch failed: {e}")

    # If ref failed, try commit endpoint to resolve tree sha
    if not meta["tree_sha"]:
        commit_url = f"{GITHUB_API}/repos/{owner}/{repo}/commits/{default_branch}"
        try:
            commit_res = _SESSION.get(commit_url, headers=headers, timeout=8)
            if commit_res.status_code == 200:
                commit_data = commit_res.json()
                meta["tree_sha"] = ((commit_data.get("commit") or {}).get("tree") or {}).get("sha")
        except Exception as e:
            print(f"⚠️  GitHub commit fetch failed: {e}")

    if not meta["tree_sha"]:
        return [], meta

    tree_url = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{meta['tree_sha']}?recursive=1"
    meta["tree_url"] = tree_url
    try:
        r = _SESSION.get(tree_url, headers=headers, timeout=12)
        meta["tree_status"] = r.status_code
        if r.status_code == 200:
            data = r.json()
            meta["truncated"] = bool(data.get("truncated", False))
            return data.get("tree", []), meta
    except Exception as e:
        print(f"⚠️  GitHub tree fetch failed: {e}")
    return [], meta


def fetch_all(owner: str, repo: str, token: Optional[str] = None) -> dict:
    """Return a bundle: repo + contributors + issues + tree."""
    print(f"📡 Fetching GitHub data for {owner}/{repo}…")
    effective_token = _effective_token(token)
    repo_info = fetch_repo(owner, repo, effective_token)
    tree, tree_meta = fetch_tree(owner, repo, effective_token, ref=repo_info.get("default_branch"))
    return {
        "repo": repo_info,
        "contributors": fetch_contributors(owner, repo, effective_token),
        "issues": fetch_issues(owner, repo, effective_token),
        "tree": tree,
        "tree_meta": tree_meta,
        "source": "github" if (effective_token and not repo_info.get("__fallback__")) else "fallback",
    }
