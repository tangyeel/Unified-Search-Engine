from fastapi import APIRouter, Query, Header, HTTPException
from db.neo4j import run_query, get_driver
from services.graph_builder import get_mock_graph
from models.schemas import ExpertResult, Node
from services import gdrive_search as gdrive_module
from services.gdrive_search import GDriveSearchEngine, AuthError, ScopeError, RateLimitError, SearchSyntaxError, GDriveSearchError
import os
from datetime import datetime

router = APIRouter()


def _score_developers(q: str, nodes: list[Node], edges) -> ExpertResult:
    """Score developers by how many edges they have to nodes matching q."""
    q_lower = q.lower()

    # Find all nodes that match the query
    relevant_ids: set[str] = set()
    for node in nodes:
        text = " ".join(str(v) for v in node.properties.values()).lower() + " " + node.id.lower()
        if q_lower in text:
            relevant_ids.add(node.id)

    # Score developers
    dev_scores: dict[str, int] = {}
    for edge in edges:
        is_dev_src = edge.source.startswith("dev:")
        is_dev_tgt = edge.target.startswith("dev:")

        if is_dev_src and edge.target in relevant_ids:
            login = edge.source[4:]
            dev_scores[login] = dev_scores.get(login, 0) + 1
        if is_dev_tgt and edge.source in relevant_ids:
            login = edge.target[4:]
            dev_scores[login] = dev_scores.get(login, 0) + 1

    # Also weight by contributions property
    node_map = {n.id: n for n in nodes}
    for dev_login, score in list(dev_scores.items()):
        dev_node = node_map.get(f"dev:{dev_login}")
        if dev_node:
            contribs = dev_node.properties.get("contributions", 0)
            dev_scores[dev_login] = score + (contribs // 20)

    if not dev_scores:
        return ExpertResult()

    best_login = max(dev_scores, key=dev_scores.__getitem__)
    best_score = dev_scores[best_login]

    # Collect related nodes for the best expert
    best_id = f"dev:{best_login}"
    related_ids = set()
    for edge in edges:
        if edge.source == best_id:
            related_ids.add(edge.target)
        if edge.target == best_id:
            related_ids.add(edge.source)

    related_nodes = [node_map[i] for i in related_ids if i in node_map]

    return ExpertResult(expert=best_login, score=best_score, related_nodes=related_nodes)


def _neo4j_expert(q: str) -> ExpertResult:
    cypher = """
    MATCH (d:Developer)-[r]-(n)
    WHERE toLower(n.name) CONTAINS toLower($q)
       OR toLower(n.title) CONTAINS toLower($q)
       OR toLower(n.description) CONTAINS toLower($q)
    WITH d, count(r) AS rel_count, d.contributions AS contribs
    RETURN d.id AS dev_id, d.name AS dev_name,
           (rel_count + coalesce(contribs, 0) / 20) AS score
    ORDER BY score DESC
    LIMIT 1
    """
    records = run_query(cypher, {"q": q})
    if not records:
        return ExpertResult()

    top = records[0]
    login = top.get("dev_name") or top.get("dev_id", "").replace("dev:", "")
    score = int(top.get("score", 0))
    return ExpertResult(expert=login, score=score)


@router.get("/expert", response_model=ExpertResult, summary="Find best expert for a topic")
def expert(q: str = Query(..., description="Topic or keyword")):
    if get_driver():
        return _neo4j_expert(q)

    all_nodes, all_edges = get_mock_graph()
    return _score_developers(q, all_nodes, all_edges)


def _gdrive_tokens():
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
    raw = os.getenv("GDRIVE_TOKENS") or ""
    if raw.strip():
        return [t.strip() for t in raw.split(",") if t.strip()]
    single = os.getenv("GDRIVE_TOKEN")
    return [single] if single else []


@router.get("/expert/drive", summary="Rank experts from Google Drive file metadata")
def expert_drive(
    q: str = Query(..., description="Task keyword"),
    limit: int = Query(30, ge=1, le=200),
    x_gdrive_token: str | None = Header(default=None, alias="X-GDrive-Token"),
):
    if x_gdrive_token:
        engine = GDriveSearchEngine([x_gdrive_token])
    else:
        try:
            ensure = getattr(gdrive_module, "_ensure_engine", None)
            engine = ensure() if callable(ensure) else None
        except Exception:
            engine = None
        if engine is None:
            tokens = _gdrive_tokens()
            if not tokens:
                raise HTTPException(422, "No Drive tokens configured.")
            engine = GDriveSearchEngine(tokens)

    try:
        resp = engine.search(q, kind="files", limit=limit).to_dict()
    except RateLimitError as e:
        raise HTTPException(429, str(e))
    except (AuthError, ScopeError) as e:
        raise HTTPException(401, str(e))
    except SearchSyntaxError as e:
        raise HTTPException(400, str(e))
    except GDriveSearchError as e:
        raise HTTPException(502, str(e))

    items = resp.get("items", [])
    experts: dict[str, dict] = {}

    def _parse_dt(value: str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None

    for item in items:
        owners = item.get("owners") or ["Unknown"]
        modified = item.get("modified_time") or item.get("modifiedTime") or ""
        modified_dt = _parse_dt(modified)
        for owner in owners:
            entry = experts.setdefault(
                owner,
                {"name": owner, "count": 0, "last_modified": modified, "files": []},
            )
            entry["count"] += 1
            if modified_dt:
                existing_dt = _parse_dt(entry.get("last_modified", "")) or modified_dt
                if modified_dt > existing_dt:
                    entry["last_modified"] = modified
            if len(entry["files"]) < 5:
                entry["files"].append({
                    "name": item.get("name"),
                    "url": item.get("web_view_link"),
                    "modified_time": modified,
                    "mime": item.get("mime_type"),
                })

    ranked = sorted(
        experts.values(),
        key=lambda e: (-e["count"], e.get("last_modified") or ""),
    )

    return {
        "query": q,
        "total_files": len(items),
        "experts": ranked[:10],
    }
