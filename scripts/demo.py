import json
from pathlib import Path
import httpx

BASE = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parent.parent

def post(path, body):
    response = httpx.post(BASE + path, json=body, timeout=30); response.raise_for_status(); return response.json()

print("1. Ingest v1")
print(post("/documents/ingest", {"path": str(ROOT / "data/ct200_manual.md")}))
nodes = httpx.get(BASE + "/search", params={"q": "pressure", "version": 1}).json()["results"]
chosen = next(n for n in nodes if n["heading"] == "Cuff pressure protection")
print("2. Pin a v1 selection to", chosen["id"])
selection = post("/selections", {"name": "Pressure safety v1", "version": 1, "node_ids": [chosen["id"]]})
print("3. Generate cases", post(f"/selections/{selection['id']}/generate", {}))
print("4. Ingest v2")
print(post("/documents/ingest", {"path": str(ROOT / "data/ct200_manual_v2.md")}))
print("5. Retrieve old generation; stale must be true")
print(json.dumps(httpx.get(BASE + f"/generations/selection/{selection['id']}").json(), indent=2))
