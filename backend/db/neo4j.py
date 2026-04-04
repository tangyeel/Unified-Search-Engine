"""
neo4j.py
Neo4j is disabled in this project. All functions below are safe no-ops.
This prevents any attempt to connect to bolt://localhost:7687.
"""

_driver = None


def get_driver():
    return None


def run_query(query: str, params: dict = None):
    return []


def close_driver():
    return None
