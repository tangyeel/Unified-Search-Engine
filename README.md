# SYSTEM DOCUMENTATION: UNIFIED ENTERPRISE SEARCH ENGINE

## 1.0 SYSTEM OVERVIEW
This repository contains the source code and operational parameters for a highly concurrent, unified enterprise search architecture. The system aggregates cross-domain data across specified third-party nodes (Slack, Google Workspace, GitHub) into a singular, normalized query interface. 

The architecture strictly enforces Role-Based Access Control (RBAC) at the network level, ensuring data retrieval is constrained by the user's authenticated permission matrix.

## 2.0 ARCHITECTURE SPECIFICATION

### 2.1 Core Components
* **Frontend Client:** React.js environment utilizing asynchronous state management and Axios for localized data rendering.
* **Backend Orchestrator:** Python 3.x environment running FastAPI over an ASGI server (Uvicorn).
* **Authentication Layer:** OAuth 2.0 and JSON Web Token (JWT) validation protocol.

### 2.2 Integration Nodes
The system executes asynchronous query dispatching to the following external APIs:
* Google Drive API (v3)
* Google Docs API (v1)
* Slack Web API
* GitHub REST API

## 3.0 SYSTEM EXECUTION PROTOCOL

### 3.1 Environment Prerequisites
Ensure the execution environment possesses the following dependencies prior to initialization:
* Python >= 3.9
* Node.js >= v16.x
* Valid API credentials for Google Cloud Console, Slack Application Directory, and GitHub Developer Settings.

### 3.2 Backend Initialization
Execute the following sub-routines to deploy the FastAPI orchestrator.

```bash
git clone [https://github.com/tangyeel/unified-search-engine.git](https://github.com/tangyeel/unified-search-engine.git)
cd unified-search-engine/backend

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt


Establish the environment variables. Construct a .env file within the /backend directory:
SECRET_KEY=insert_jwt_secret_key_here
ACCESS_TOKEN_EXPIRE_MINUTES=30
GITHUB_CLIENT_ID=insert_github_id_here
GITHUB_CLIENT_SECRET=insert_github_secret_here
SLACK_BOT_TOKEN=insert_slack_token_here
GOOGLE_CREDENTIALS_JSON=insert_path_to_json_here




