# TracePath Backend (DocuPulse)

FastAPI backend for the DocuPulse/TracePath knowledge graph demo.

## Quick Start (Local)

```powershell
cd C:\Users\Aditya\Desktop\Eclipse\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Open the docs UI:
- http://127.0.0.1:8000/docs

## Environment Variables

Copy the example env file and update if needed:

```powershell
copy .env.example .env
```

Supported vars:
- `NEO4J_URI` (default: `bolt://localhost:7687`)
- `NEO4J_USER` (default: `neo4j`)
- `NEO4J_PASSWORD` (default: `password`)
- `GITHUB_TOKEN` (optional, for real GitHub access)
- `SLACK_TOKEN` / `SLACK_TOKENS` (Slack user tokens, xoxp-... recommended)
- `GDRIVE_TOKEN` / `GDRIVE_TOKENS` (Google Drive OAuth access tokens)

If Neo4j is not reachable, the API automatically falls back to mock data.

## API Endpoints

### Health
`GET /health`

### Search
`GET /search?q=keyword`

### Graph
`GET /graph?q=*`

### Expert
`GET /expert?q=topic`

### GitHub Search (live, no storage)
`GET /search/github?q=react&kind=code`

Optional headers:
- `X-GitHub-Token: <token>`

Optional setup:
- `POST /search/github/configure` with body:
```json
{"tokens":["ghp_xxx","ghp_yyy"]}
```

### Slack Search (live, no storage)
`GET /search/slack?q=incident&kind=messages`

Setup:
- `POST /search/slack/configure` with body:
```json
{"tokens":["xoxp_xxx","xoxp_yyy"]}
```
Or set `SLACK_TOKEN` / `SLACK_TOKENS` in `.env` and skip configure.

### Google Drive Search (live, no storage)
`GET /search/gdrive?q=invoice&kind=files`

Setup:
- `POST /search/gdrive/configure` with body:
```json
{"tokens":["ya29.xxx"]}
```
Or set `GDRIVE_TOKEN` / `GDRIVE_TOKENS` in `.env` and skip configure.

### Unified Search (GitHub + Slack + Drive)
`GET /search/unified?q=invoice&sources=github,slack,gdrive`

Headers (optional):
- `X-GitHub-Token`
- `X-Slack-Token`
- `X-GDrive-Token`
If headers are omitted, the API uses tokens from `.env`.

### Provider Health
`GET /health/sources`
Returns token + connectivity status for GitHub, Slack, and Google Drive.

### Indexed Search
Build an index from live providers, then query it quickly:

`POST /search/index/ingest?q=invoice&sources=github,slack,gdrive`

`GET /search/index?q=invoice`

`GET /search/index/status`

### Ingest GitHub
`POST /fetch/github`

Body:
```json
{"owner":"acme","repo":"payment-api","token":null}
```

Notes:
- If `token` is omitted, `GITHUB_TOKEN` will be used.
- If neither is provided, the service will fall back to dummy data.
- You can also pass the token via header: `X-GitHub-Token: <token>`.

### Ingest Local
`POST /fetch/local`

Body:
```json
{"file_path":"C:\\Users\\Aditya\\Desktop\\Eclipse\\backend\\sample_data.json"}
```

## Docker

Build and run from the backend folder:

```powershell
docker build -t tracepath-backend .
docker run --rm -p 8000:8000 --env-file .env tracepath-backend
```
