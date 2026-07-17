# CT-200 Traceable QA API

A FastAPI backend that ingests a medical-device manual as a versioned tree, creates immutable version-pinned selections, generates validated QA test-case ideas, and reports when their source requirements become stale.

> The assignment PDF referenced two files that were not delivered. The repository therefore includes purpose-built replacement manuals with duplicate headings, skipped heading levels, Setext headings, fenced heading-like text, tables, and meaningful v2 changes. Replace them with official files if supplied later.

## Quick start

Requires Python 3.9+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

The application loads `.env` automatically. The default SQLite database and JSON generation store are created under `data/`.

Open `http://127.0.0.1:8000` (it redirects to the interactive API documentation). In another terminal, run:

## Docker run (easiest option)

This project now includes a Docker setup so your friend can run it without installing Python or dependencies manually.

### Prerequisites

- Install Docker Desktop (or Docker Engine) on the machine running the app.

### Run the API

```bash
docker compose up --build
```

Then open:

- `http://127.0.0.1:8000` for the API
- `http://127.0.0.1:8000/docs` for the interactive Swagger UI

To stop it:

```bash
docker compose down
```

The container stores its SQLite database and generated JSON files in the local `data/` folder so they persist between restarts.

### Run the demo script

In a second terminal:

```bash
docker compose exec api python scripts/demo.py
```

```bash
source .venv/bin/activate
python scripts/demo.py
```

The script ingests v1, creates a pinned selection, generates test ideas, ingests v2, and retrieves the generation with `stale: true`.

## Tests

```bash
pytest -q
```

## LLM configuration

The safe default `LLM_MODE=mock` makes the complete flow deterministic without credentials. This is a demonstration fallback, not a claim that mock output is LLM-powered. For an evaluated live demonstration, configure any OpenAI-compatible provider by setting `LLM_MODE=live`, `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` in `.env`. Live responses are Pydantic-validated, checked for invented source IDs, and retried with validation feedback. After the retry budget, the API returns 502 and stores nothing.

Generation is idempotent per selection by default: repeated requests return the stored result. Send `{"force": true}` to explicitly replace it. The JSON-file generation store is intentionally separated from relational data and is explained in [APPROACH.md](APPROACH.md).

## API summary

- `POST /documents/ingest`
- `GET /sections?version=1`
- `GET /nodes/{logical_id}?version=1`
- `GET /search?q=pressure&version=1`
- `GET /nodes/{logical_id}/changes`
- `POST /selections`
- `POST /selections/{id}/generate`
- `GET /generations/selection/{id}`
- `GET /generations/node/{logical_id}`

Browse/search endpoints accept `document_key` (default `ct-200`) and an optional version. Version resolution and staleness checks are scoped to that document.

## Submission checklist

1. Replace the author name, email, and repository placeholders with the candidate's real details.
2. Create a GitHub repository and push the existing incremental commit history.
3. If possible, configure a real LLM provider and capture one successful live run.
4. Run `pytest -q` and `python scripts/demo.py` before submitting.
5. Keep the missing-input disclosure unless the official manuals are obtained and substituted.
