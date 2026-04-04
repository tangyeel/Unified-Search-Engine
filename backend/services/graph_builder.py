"""
graph_builder.py
Converts raw GitHub / local data into graph nodes + relationships.
Writes to Neo4j when available; falls back to an in-memory store for demo.
"""

from db.neo4j import run_query, get_driver
from models.schemas import Node, Edge

# ── In-memory mock graph (fallback when Neo4j is offline) ───────────────────

_mock_nodes: dict[str, Node] = {}
_mock_edges: list[Edge] = []


def _upsert_mock_node(node: Node):
    _mock_nodes[node.id] = node


def _upsert_mock_edge(edge: Edge):
    key = (edge.source, edge.target, edge.relationship)
    if not any(
        (e.source, e.target, e.relationship) == key for e in _mock_edges
    ):
        _mock_edges.append(edge)


def get_mock_graph():
    return list(_mock_nodes.values()), _mock_edges


# ── Neo4j helpers ────────────────────────────────────────────────────────────

def _neo4j_upsert_developer(login: str, props: dict):
    run_query(
        "MERGE (d:Developer {id: $id}) SET d += $props",
        {"id": f"dev:{login}", "props": {"name": login, **props}},
    )


def _neo4j_upsert_repo(name: str, props: dict):
    run_query(
        "MERGE (r:Repository {id: $id}) SET r += $props",
        {"id": f"repo:{name}", "props": {"name": name, **props}},
    )


def _neo4j_upsert_issue(issue_id: str, props: dict):
    run_query(
        "MERGE (i:Issue {id: $id}) SET i += $props",
        {"id": issue_id, "props": props},
    )


def _neo4j_upsert_document(doc_id: str, props: dict):
    run_query(
        "MERGE (doc:Document {id: $id}) SET doc += $props",
        {"id": doc_id, "props": props},
    )


def _neo4j_upsert_folder(folder_id: str, props: dict):
    run_query(
        "MERGE (f:Folder {id: $id}) SET f += $props",
        {"id": folder_id, "props": props},
    )


def _neo4j_upsert_file(file_id: str, props: dict):
    run_query(
        "MERGE (f:File {id: $id}) SET f += $props",
        {"id": file_id, "props": props},
    )


def _neo4j_relate(src_id: str, rel: str, tgt_id: str):
    run_query(
        f"""
        MATCH (a {{id: $src}}), (b {{id: $tgt}})
        MERGE (a)-[:{rel}]->(b)
        """,
        {"src": src_id, "tgt": tgt_id},
    )


def ensure_fulltext_index():
    """Create a fulltext index for search if it doesn't exist."""
    try:
        run_query(
            """
            CALL db.index.fulltext.createNodeIndex(
              'tracepath_idx',
              ['Repository','Developer','Issue','Document','Folder','File'],
              ['name','title','description','path','author']
            )
            """,
            {},
        )
    except Exception:
        # Index may already exist or Neo4j may be unavailable
        pass


# ── Public build functions ───────────────────────────────────────────────────

def build_from_github(data: dict):
    """Ingest fetched GitHub bundle into the graph."""
    repo_info = data.get("repo", {})
    repo_name = repo_info.get("name", "unknown")
    repo_id = f"repo:{repo_name}"

    # --- Repository node ---
    repo_props = {
        "description": repo_info.get("description", ""),
        "language": repo_info.get("language", ""),
        "stars": repo_info.get("stargazers_count", 0),
    }
    _neo4j_upsert_repo(repo_name, repo_props)
    _upsert_mock_node(Node(id=repo_id, label="Repository", properties={"name": repo_name, **repo_props}))

    # --- Repo file tree (folders + files) ---
    tree = data.get("tree", [])
    if tree:
        ensure_fulltext_index()
        folder_nodes: dict[str, Node] = {}
        file_nodes: dict[str, Node] = {}

        for item in tree:
            path = item.get("path", "")
            kind = item.get("type", "")
            if not path:
                continue

            parts = path.split("/")
            parent_id = repo_id
            current_path = ""

            for i, part in enumerate(parts):
                current_path = f"{current_path}/{part}" if current_path else part
                is_last = i == len(parts) - 1

                if is_last and kind == "blob":
                    file_id = f"file:{repo_name}:{current_path}"
                    props = {"name": part, "path": current_path, "repo": repo_name}
                    _neo4j_upsert_file(file_id, props)
                    file_nodes[file_id] = Node(id=file_id, label="File", properties=props)
                    _neo4j_relate(parent_id, "CONTAINS", file_id)
                    _upsert_mock_edge(Edge(source=parent_id, target=file_id, relationship="CONTAINS"))
                else:
                    folder_id = f"folder:{repo_name}:{current_path}"
                    if folder_id not in folder_nodes:
                        props = {"name": part, "path": current_path, "repo": repo_name}
                        _neo4j_upsert_folder(folder_id, props)
                        folder_nodes[folder_id] = Node(id=folder_id, label="Folder", properties=props)
                    _neo4j_relate(parent_id, "CONTAINS", folder_id)
                    _upsert_mock_edge(Edge(source=parent_id, target=folder_id, relationship="CONTAINS"))
                    parent_id = folder_id

        for node in folder_nodes.values():
            _upsert_mock_node(node)
        for node in file_nodes.values():
            _upsert_mock_node(node)

    # --- Contributor nodes + WORKED_ON edges ---
    for contrib in data.get("contributors", []):
        login = contrib.get("login", "unknown")
        dev_id = f"dev:{login}"
        dev_props = {"contributions": contrib.get("contributions", 0)}
        _neo4j_upsert_developer(login, dev_props)
        _upsert_mock_node(Node(id=dev_id, label="Developer", properties={"name": login, **dev_props}))
        _neo4j_relate(dev_id, "WORKED_ON", repo_id)
        _upsert_mock_edge(Edge(source=dev_id, target=repo_id, relationship="WORKED_ON"))

    # --- Issue nodes + HAS_ISSUE edges ---
    for issue in data.get("issues", []):
        issue_num = issue.get("number", 0)
        issue_id = f"issue:{repo_name}:{issue_num}"
        issue_props = {
            "title": issue.get("title", ""),
            "state": issue.get("state", "open"),
            "body": (issue.get("body") or "")[:300],
        }
        _neo4j_upsert_issue(issue_id, issue_props)
        _upsert_mock_node(Node(id=issue_id, label="Issue", properties=issue_props))
        _neo4j_relate(repo_id, "HAS_ISSUE", issue_id)
        _upsert_mock_edge(Edge(source=repo_id, target=issue_id, relationship="HAS_ISSUE"))

        # Issue author → AUTHORED → Issue
        author = (issue.get("user") or {}).get("login", "")
        if author:
            author_id = f"dev:{author}"
            _neo4j_upsert_developer(author, {})
            _upsert_mock_node(Node(id=author_id, label="Developer", properties={"name": author}))
            _neo4j_relate(author_id, "AUTHORED", issue_id)
            _upsert_mock_edge(Edge(source=author_id, target=issue_id, relationship="AUTHORED"))

    print(f"✅ GitHub graph built for repo '{repo_name}'")


def build_from_local(data: dict):
    """Ingest local JSON data into the graph."""

    # Repositories
    for repo in data.get("repositories", []):
        name = repo.get("name", "unknown")
        repo_id = f"repo:{name}"
        props = {k: v for k, v in repo.items() if k != "name"}
        _neo4j_upsert_repo(name, props)
        _upsert_mock_node(Node(id=repo_id, label="Repository", properties={"name": name, **props}))

    # Developers
    for dev in data.get("developers", []):
        login = dev.get("login", "unknown")
        dev_id = f"dev:{login}"
        props = {k: v for k, v in dev.items() if k not in ("login", "repos")}
        _neo4j_upsert_developer(login, props)
        _upsert_mock_node(Node(id=dev_id, label="Developer", properties={"name": login, **props}))
        for repo_name in dev.get("repos", []):
            repo_id = f"repo:{repo_name}"
            _neo4j_relate(dev_id, "WORKED_ON", repo_id)
            _upsert_mock_edge(Edge(source=dev_id, target=repo_id, relationship="WORKED_ON"))

    # Issues
    for i, issue in enumerate(data.get("issues", [])):
        repo_name = issue.get("repo", "unknown")
        issue_id = f"issue:{repo_name}:{i}"
        props = {"title": issue.get("title", ""), "state": issue.get("state", "open")}
        _neo4j_upsert_issue(issue_id, props)
        _upsert_mock_node(Node(id=issue_id, label="Issue", properties=props))
        repo_id = f"repo:{repo_name}"
        _neo4j_relate(repo_id, "HAS_ISSUE", issue_id)
        _upsert_mock_edge(Edge(source=repo_id, target=issue_id, relationship="HAS_ISSUE"))
        author = issue.get("author", "")
        if author:
            dev_id = f"dev:{author}"
            _neo4j_relate(dev_id, "AUTHORED", issue_id)
            _upsert_mock_edge(Edge(source=dev_id, target=issue_id, relationship="AUTHORED"))

    # Documents
    for doc in data.get("documents", []):
        title = doc.get("title", "untitled")
        doc_id = f"doc:{title.lower().replace(' ', '-')}"
        props = {"title": title, "author": doc.get("author", ""), "related_to": doc.get("related_to", "")}
        _neo4j_upsert_document(doc_id, props)
        _upsert_mock_node(Node(id=doc_id, label="Document", properties=props))
        author = doc.get("author", "")
        if author:
            dev_id = f"dev:{author}"
            _neo4j_relate(dev_id, "AUTHORED", doc_id)
            _upsert_mock_edge(Edge(source=dev_id, target=doc_id, relationship="AUTHORED"))
        related = doc.get("related_to", "")
        if related:
            repo_id = f"repo:{related}"
            _neo4j_relate(doc_id, "RELATED_TO", repo_id)
            _upsert_mock_edge(Edge(source=doc_id, target=repo_id, relationship="RELATED_TO"))

    print("✅ Local graph built")
