from __future__ import annotations

from typing import Iterable

import requests
from requests.adapters import HTTPAdapter

try:
    import certifi
except Exception:  # pragma: no cover - certifi ships with requests
    certifi = None

try:
    from urllib3.util.retry import Retry
except Exception:  # pragma: no cover
    Retry = None


def build_session(
    *,
    retries: int = 3,
    backoff: float = 0.5,
    status_forcelist: Iterable[int] = (429, 500, 502, 503, 504),
) -> requests.Session:
    session = requests.Session()
    if Retry is not None:
        retry = Retry(
            total=retries,
            connect=retries,
            read=retries,
            backoff_factor=backoff,
            status_forcelist=status_forcelist,
            allowed_methods={"GET", "POST"},
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
    if certifi is not None:
        session.verify = certifi.where()
    return session
