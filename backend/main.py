"""
TracePath Backend — main.py
Run with:  uvicorn main:app --reload --port 8000
"""

import os
from dotenv import load_dotenv
from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from db.neo4j import close_driver
from api.search import router as search_router
from api.graph import router as graph_router
from api.expert import router as expert_router
from services import github as gh_service
from services import local as local_service
from services import graph_builder
from services.github_search import router as github_search_router
from services.slack_search import router as slack_search_router
from services.gdrive_search import router as gdrive_search_router
from services.unified_search import router as unified_search_router
from services.provider_health import router as provider_health_router
from services.indexed_search import router as indexed_search_router
from services.github_profile import router as github_profile_router
from api.github_data import router as github_data_router
from models.schemas import (
    GitHubFetchRequest,
    LocalFetchRequest,
    StatusResponse,
)

load_dotenv()
SKIP_NEO4J = os.getenv("SKIP_NEO4J", "0") == "1"


# ── Startup / shutdown ───────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-load demo data so the graph is never empty on first request
    if not SKIP_NEO4J:
        graph_builder.ensure_fulltext_index()
    local_data = local_service.load_local()
    graph_builder.build_from_local(local_data)
    if SKIP_NEO4J:
        print("🚀 TracePath backend ready (Neo4j skipped)")
    else:
        print("🚀 TracePath backend ready")
    yield
    if not SKIP_NEO4J:
        close_driver()


# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="TracePath API",
    description="Knowledge graph search engine — GitHub + local files",
    version="1.0.0",
    lifespan=lifespan,
)

_cors_raw = os.getenv("CORS_ALLOW_ORIGINS", "*")
if _cors_raw.strip() == "*":
    _cors_origins = ["*"]
else:
    _cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────

app.include_router(search_router, tags=["Search"])
app.include_router(graph_router,  tags=["Graph"])
app.include_router(expert_router, tags=["Expert"])
app.include_router(github_search_router)
app.include_router(slack_search_router)
app.include_router(gdrive_search_router)
app.include_router(unified_search_router)
app.include_router(provider_health_router)
app.include_router(indexed_search_router)
app.include_router(github_profile_router)
app.include_router(github_data_router)


# ── Ingest endpoints ─────────────────────────────────────────────────────────

@app.post("/fetch/github", response_model=StatusResponse, tags=["Ingest"])
def fetch_github(
    req: GitHubFetchRequest,
    x_github_token: str | None = Header(default=None, alias="X-GitHub-Token"),
):
    """Fetch GitHub repo data and insert into the knowledge graph."""
    token = x_github_token or req.token
    data = gh_service.fetch_all(req.owner, req.repo, token)
    tree = data.get("tree", [])
    tree_meta = data.get("tree_meta", {})
    graph_builder.build_from_github(data)
    return StatusResponse(
        status="ok",
        message=f"GitHub data fetched for {req.owner}/{req.repo}",
        data={
            "repo": data["repo"].get("full_name"),
            "contributors": len(data["contributors"]),
            "issues": len(data["issues"]),
            "tree_count": len(tree),
            "tree_sample": [item.get("path") for item in tree[:5]],
            "source": data.get("source", "unknown"),
            "tree_meta": tree_meta,
        },
    )


@app.post("/fetch/local", response_model=StatusResponse, tags=["Ingest"])
def fetch_local(req: LocalFetchRequest):
    """Load local JSON file into the knowledge graph."""
    data = local_service.load_local(req.file_path)
    graph_builder.build_from_local(data)
    return StatusResponse(
        status="ok",
        message=f"Local data loaded from '{req.file_path or 'demo'}'",
        data={
            "repos": len(data.get("repositories", [])),
            "developers": len(data.get("developers", [])),
            "issues": len(data.get("issues", [])),
            "documents": len(data.get("documents", [])),
        },
    )


# ── Health check ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["Meta"])
def health():
    from db.neo4j import get_driver
    nodes, edges = graph_builder.get_mock_graph()
    return {
        "status": "ok",
        "neo4j": "connected" if get_driver() else "mock-mode",
        "graph": {"nodes": len(nodes), "edges": len(edges)},
    }
