from __future__ import annotations

import os
import requests
from typing import Optional

from fastapi import APIRouter, Header

router = APIRouter(tags=["Health"])


def _pick_token(header_token: Optional[str], env_single: str, env_multi: str) -> Optional[str]:
    if header_token:
        return header_token
    if env_multi.strip():
        return env_multi.split(",")[0].strip()
    return env_single if env_single else None


@router.get("/health/sources")
def health_sources(
    x_github_token: str | None = Header(default=None, alias="X-GitHub-Token"),
    x_slack_token: str | None = Header(default=None, alias="X-Slack-Token"),
    x_gdrive_token: str | None = Header(default=None, alias="X-GDrive-Token"),
):
    github_token = _pick_token(
        x_github_token,
        os.getenv("GITHUB_TOKEN", ""),
        os.getenv("GITHUB_TOKENS", ""),
    )
    slack_token = _pick_token(
        x_slack_token,
        os.getenv("SLACK_TOKEN", ""),
        os.getenv("SLACK_TOKENS", ""),
    )
    gdrive_token = _pick_token(
        x_gdrive_token,
        os.getenv("GDRIVE_TOKEN", ""),
        os.getenv("GDRIVE_TOKENS", ""),
    )
    gdrive_refresh = os.getenv("GDRIVE_REFRESH_TOKEN", "")
    gdrive_client_id = os.getenv("GDRIVE_CLIENT_ID", "")
    gdrive_client_secret = os.getenv("GDRIVE_CLIENT_SECRET", "")

    out = {"github": {}, "slack": {}, "gdrive": {}}

    # --- GitHub ---
    if not github_token:
        out["github"] = {"status": "missing_token"}
    else:
        try:
            resp = requests.get(
                "https://api.github.com/rate_limit",
                headers={"Authorization": f"Bearer {github_token}"},
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json().get("rate", {})
                out["github"] = {
                    "status": "ok",
                    "limit": data.get("limit"),
                    "remaining": data.get("remaining"),
                    "reset": data.get("reset"),
                }
            else:
                out["github"] = {"status": "error", "code": resp.status_code}
        except Exception as e:
            out["github"] = {"status": "error", "detail": str(e)}

    # --- Slack ---
    if not slack_token:
        out["slack"] = {"status": "missing_token"}
    else:
        try:
            resp = requests.get(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {slack_token}"},
                timeout=8,
            )
            data = resp.json()
            if data.get("ok"):
                out["slack"] = {
                    "status": "ok",
                    "team": data.get("team"),
                    "user": data.get("user"),
                    "team_id": data.get("team_id"),
                }
            else:
                out["slack"] = {"status": "error", "error": data.get("error", "unknown")}
        except Exception as e:
            out["slack"] = {"status": "error", "detail": str(e)}

    # --- Google Drive ---
    if not gdrive_token and gdrive_refresh and gdrive_client_id and gdrive_client_secret:
        try:
            resp = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": gdrive_client_id,
                    "client_secret": gdrive_client_secret,
                    "refresh_token": gdrive_refresh,
                    "grant_type": "refresh_token",
                },
                timeout=8,
            )
            data = resp.json()
            access = data.get("access_token")
            if access:
                info = requests.get(
                    "https://www.googleapis.com/oauth2/v3/tokeninfo",
                    params={"access_token": access},
                    timeout=8,
                ).json()
                out["gdrive"] = {
                    "status": "ok",
                    "mode": "refresh_token",
                    "email": info.get("email", "unknown"),
                    "scope": info.get("scope"),
                    "expires_in": data.get("expires_in"),
                }
            else:
                out["gdrive"] = {"status": "error", "error": data.get("error_description", "refresh_failed")}
        except Exception as e:
            out["gdrive"] = {"status": "error", "detail": str(e)}
    elif not gdrive_token:
        out["gdrive"] = {"status": "missing_token"}
    else:
        try:
            resp = requests.get(
                "https://www.googleapis.com/oauth2/v3/tokeninfo",
                params={"access_token": gdrive_token},
                timeout=8,
            )
            data = resp.json()
            if "error" not in data:
                out["gdrive"] = {
                    "status": "ok",
                    "email": data.get("email"),
                    "scope": data.get("scope"),
                    "expires_in": data.get("expires_in"),
                }
            else:
                out["gdrive"] = {"status": "error", "error": data.get("error_description", data.get("error"))}
        except Exception as e:
            out["gdrive"] = {"status": "error", "detail": str(e)}

    return out
