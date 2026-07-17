from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from .generation import list_generations, load_generation, now_iso, request_cases, store_generation
from .models import NodeSnapshot, Selection, SelectionItem
from .schemas import GenerateRequest, IngestRequest, SelectionCreate
from .services import compare_node, document_key_for_snapshot, ingest, resolve_version, search_nodes, selection_text

@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    yield

app = FastAPI(title="CT-200 Traceable QA API", version="1.0.0", lifespan=lifespan)

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")

@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "CT-200 Traceable QA API"}

def node_dict(node: NodeSnapshot):
    return {"id": node.logical_id, "snapshot_id": node.id, "version": node.version.number,
            "heading": node.heading, "level": node.level, "body": node.body,
            "full_text": node.full_text, "content_hash": node.content_hash,
            "parent_id": node.parent_logical_id}

@app.post("/documents/ingest")
def ingest_document(body: IngestRequest, db: Session = Depends(get_db)):
    path = Path(body.path).resolve()
    if not path.is_file() or path.suffix.lower() != ".md":
        raise HTTPException(400, "path must point to an existing Markdown file")
    try:
        version = ingest(db, path, body.document_key)
        return {"document": body.document_key, "version": version.number, "source_hash": version.source_hash, "nodes": len(version.nodes)}
    except ValueError as exc:
        raise HTTPException(422, str(exc))

@app.get("/sections")
def sections(version: Optional[int] = None, document_key: str = "ct-200", db: Session = Depends(get_db)):
    try: v = resolve_version(db, version, document_key)
    except LookupError as exc: raise HTTPException(404, str(exc))
    roots = db.scalars(select(NodeSnapshot).where(NodeSnapshot.version_id == v.id, NodeSnapshot.parent_logical_id.is_(None)).order_by(NodeSnapshot.position)).all()
    root_ids = [node.logical_id for node in roots]
    nodes = db.scalars(select(NodeSnapshot).where(NodeSnapshot.version_id == v.id, NodeSnapshot.parent_logical_id.in_(root_ids)).order_by(NodeSnapshot.position)).all() if root_ids else []
    return {"document": document_key, "version": v.number, "sections": [node_dict(n) for n in nodes]}

@app.get("/nodes/{node_id}")
def get_node(node_id: str, version: Optional[int] = None, document_key: str = "ct-200", db: Session = Depends(get_db)):
    try: v = resolve_version(db, version, document_key)
    except LookupError as exc: raise HTTPException(404, str(exc))
    node = db.scalar(select(NodeSnapshot).where(NodeSnapshot.version_id == v.id, NodeSnapshot.logical_id == node_id))
    if not node: raise HTTPException(404, "Node not found in requested version")
    children = db.scalars(select(NodeSnapshot).where(NodeSnapshot.version_id == v.id, NodeSnapshot.parent_logical_id == node.logical_id).order_by(NodeSnapshot.position)).all()
    return {**node_dict(node), "children": [node_dict(c) for c in children]}

@app.get("/search")
def search(q: str = Query(min_length=1), version: Optional[int] = None, document_key: str = "ct-200", db: Session = Depends(get_db)):
    try: v = resolve_version(db, version, document_key)
    except LookupError as exc: raise HTTPException(404, str(exc))
    return {"version": v.number, "results": [node_dict(n) for n in search_nodes(db, v.id, q)]}

@app.get("/nodes/{node_id}/changes")
def changes(node_id: str, db: Session = Depends(get_db)):
    try: return compare_node(db, node_id)
    except LookupError as exc: raise HTTPException(404, str(exc))

@app.post("/selections", status_code=201)
def create_selection(body: SelectionCreate, db: Session = Depends(get_db)):
    try: version = resolve_version(db, body.version, body.document_key)
    except LookupError as exc: raise HTTPException(404, str(exc))
    snapshots = db.scalars(select(NodeSnapshot).where(NodeSnapshot.version_id == version.id, NodeSnapshot.logical_id.in_(set(body.node_ids)))).all()
    if len(snapshots) != len(set(body.node_ids)):
        raise HTTPException(400, "One or more node IDs do not exist in the requested version")
    selection = Selection(name=body.name); db.add(selection); db.flush()
    for snapshot in snapshots: db.add(SelectionItem(selection_id=selection.id, snapshot_id=snapshot.id))
    db.commit(); db.refresh(selection)
    return {"id": selection.id, "name": selection.name, "version": version.number, "nodes": [node_dict(i.snapshot) for i in selection.items]}

@app.post("/selections/{selection_id}/generate")
def generate(selection_id: int, body: GenerateRequest, db: Session = Depends(get_db)):
    selection = db.get(Selection, selection_id)
    if not selection: raise HTTPException(404, "Selection not found")
    try: existing = load_generation(selection_id)
    except RuntimeError as exc: raise HTTPException(500, str(exc))
    if existing and not body.force: return {**existing, "reused": True}
    node_ids = [i.snapshot.logical_id for i in selection.items]
    try: cases, model = request_cases(selection_text(selection), node_ids)
    except RuntimeError as exc: raise HTTPException(502, str(exc))
    record = {"selection_id": selection.id, "document_key": document_key_for_snapshot(selection.items[0].snapshot), "created_at": now_iso(), "model": model,
              "source_snapshots": [{"node_id": i.snapshot.logical_id, "version": i.snapshot.version.number, "content_hash": i.snapshot.content_hash} for i in selection.items],
              "test_cases": cases.model_dump()["test_cases"]}
    store_generation(record)
    return {**record, "reused": False}

def with_staleness(record: dict, db: Session):
    latest = resolve_version(db, None, record.get("document_key", "ct-200"))
    impacts = []
    for source in record["source_snapshots"]:
        current = db.scalar(select(NodeSnapshot).where(NodeSnapshot.version_id == latest.id, NodeSnapshot.logical_id == source["node_id"]))
        status = "removed" if not current else ("fresh" if current.content_hash == source["content_hash"] else "stale")
        impacts.append({**source, "latest_version": latest.number, "status": status,
                        "current_hash": current.content_hash if current else None})
    return {**record, "stale": any(i["status"] != "fresh" for i in impacts), "impact": impacts}

@app.get("/generations/selection/{selection_id}")
def generation_by_selection(selection_id: int, db: Session = Depends(get_db)):
    try: record = load_generation(selection_id)
    except RuntimeError as exc: raise HTTPException(500, str(exc))
    if not record: raise HTTPException(404, "Generation not found")
    return with_staleness(record, db)

@app.get("/generations/node/{node_id}")
def generations_by_node(node_id: str, db: Session = Depends(get_db)):
    records = []
    try:
        for record in list_generations():
            if any(s["node_id"] == node_id for s in record["source_snapshots"]):
                records.append(with_staleness(record, db))
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))
    return {"node_id": node_id, "generations": records}
