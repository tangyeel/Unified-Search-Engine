from pydantic import BaseModel
from typing import Optional, List, Any


# ── Inbound request bodies ──────────────────────────────────────────────────

class GitHubFetchRequest(BaseModel):
    owner: str
    repo: str
    token: Optional[str] = None          # Personal Access Token (optional)


class LocalFetchRequest(BaseModel):
    file_path: str                        # Path to local JSON file


# ── Graph primitives ────────────────────────────────────────────────────────

class Node(BaseModel):
    id: str
    label: str                            # Developer | Repository | Issue | Document
    properties: dict = {}


class Edge(BaseModel):
    source: str
    target: str
    relationship: str                     # WORKED_ON | HAS_ISSUE | AUTHORED | RELATED_TO
    properties: dict = {}


# ── API response shapes ──────────────────────────────────────────────────────

class SearchResult(BaseModel):
    nodes: List[Node] = []
    relationships: List[Edge] = []
    total: int = 0


class GraphData(BaseModel):
    nodes: List[Node] = []
    edges: List[Edge] = []


class ExpertResult(BaseModel):
    expert: Optional[str] = None
    score: int = 0
    related_nodes: List[Node] = []


class StatusResponse(BaseModel):
    status: str
    message: str
    data: Optional[Any] = None
