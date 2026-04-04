from fastapi import APIRouter, Query
from db.neo4j import run_query, get_driver
from services.graph_builder import get_mock_graph
from models.schemas import GraphData, Node, Edge

router = APIRouter()


def _neo4j_graph(q: str) -> GraphData:
    cypher = """
    MATCH (n)
    WHERE toLower(n.name) CONTAINS toLower($q)
       OR toLower(n.title) CONTAINS toLower($q)
    OPTIONAL MATCH (n)-[r]-(m)
    RETURN
        n.id AS nid, labels(n)[0] AS nlabel, properties(n) AS nprops,
        type(r) AS rel,
        m.id AS mid, labels(m)[0] AS mlabel, properties(m) AS mprops
    LIMIT 100
    """
    records = run_query(cypher, {"q": q})

    nodes: dict[str, Node] = {}
    edges: list[Edge] = []

    for rec in records:
        nid = rec.get("nid")
        if nid and nid not in nodes:
            nodes[nid] = Node(id=nid, label=rec.get("nlabel", ""), properties=rec.get("nprops", {}))
        mid = rec.get("mid")
        if mid and mid not in nodes:
            nodes[mid] = Node(id=mid, label=rec.get("mlabel", ""), properties=rec.get("mprops", {}))
        if rec.get("rel") and nid and mid:
            edges.append(Edge(source=nid, target=mid, relationship=rec["rel"]))

    return GraphData(nodes=list(nodes.values()), edges=edges)


def _mock_graph(q: str) -> GraphData:
    q_lower = q.lower()
    all_nodes, all_edges = get_mock_graph()

    if not q_lower or q_lower == "*":
        return GraphData(nodes=all_nodes, edges=all_edges)

    matched_ids: set[str] = set()
    for node in all_nodes:
        text = " ".join(str(v) for v in node.properties.values()).lower() + " " + node.id.lower()
        if q_lower in text:
            matched_ids.add(node.id)

    # Expand 1-hop
    for edge in all_edges:
        if edge.source in matched_ids:
            matched_ids.add(edge.target)
        if edge.target in matched_ids:
            matched_ids.add(edge.source)

    node_map = {n.id: n for n in all_nodes}
    result_nodes = [node_map[i] for i in matched_ids if i in node_map]
    result_edges = [e for e in all_edges if e.source in matched_ids and e.target in matched_ids]

    return GraphData(nodes=result_nodes, edges=result_edges)


@router.get("/graph", response_model=GraphData, summary="Graph data for visualization")
def graph(q: str = Query("*", description="Filter keyword (* = entire graph)")):
    if get_driver():
        return _neo4j_graph(q)
    return _mock_graph(q)
