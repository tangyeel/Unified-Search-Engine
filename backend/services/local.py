import json
import os
from typing import Optional

# ── Embedded demo data (used when no file_path is provided) ─────────────────

DEMO_DATA = {
    "repositories": [
        {"name": "auth-service", "owner": "priya", "language": "Node.js",
         "description": "JWT authentication microservice"},
        {"name": "data-pipeline", "owner": "rahul", "language": "Python",
         "description": "ETL pipeline for analytics warehouse"},
    ],
    "developers": [
        {"login": "aditya", "contributions": 87, "repos": ["payment-api"]},
        {"login": "priya",  "contributions": 54, "repos": ["auth-service"]},
        {"login": "rahul",  "contributions": 23, "repos": ["data-pipeline"]},
    ],
    "issues": [
        {"title": "Database connection pool exhaustion", "repo": "data-pipeline",
         "author": "rahul", "state": "open"},
        {"title": "Token refresh race condition",        "repo": "auth-service",
         "author": "priya", "state": "closed"},
    ],
    "documents": [
        {"title": "API Design Guidelines",   "author": "aditya",
         "related_to": "payment-api"},
        {"title": "Deployment Runbook",      "author": "rahul",
         "related_to": "data-pipeline"},
        {"title": "Auth Flow Architecture",  "author": "priya",
         "related_to": "auth-service"},
    ],
}


def load_local(file_path: Optional[str] = None) -> dict:
    """Load graph seed data from a JSON file or return embedded demo data."""
    if file_path and os.path.isfile(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            print(f"📂 Loaded local data from {file_path}")
            return data
        except Exception as e:
            print(f"⚠️  Could not read {file_path}: {e}")

    print("📂 Using embedded demo data.")
    return DEMO_DATA
