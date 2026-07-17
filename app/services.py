from __future__ import annotations

import hashlib
import json
import uuid
from difflib import SequenceMatcher, unified_diff
from pathlib import Path
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from .models import Document, DocumentVersion, LogicalNode, NodeSnapshot, Selection
from .parser import parse_markdown

def stable_id(document_key: str, identity_path: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"tri9t:{document_key}:{identity_path}"))

def ingest(db: Session, path: Path, document_key: str = "ct-200") -> DocumentVersion:
    text = path.read_text(encoding="utf-8")
    digest = hashlib.sha256(text.encode()).hexdigest()
    parsed = parse_markdown(text)
    document = db.scalar(select(Document).where(Document.key == document_key))
    if not document:
        document = Document(key=document_key, title=parsed[0].heading)
        db.add(document); db.flush()
    existing = db.scalar(select(DocumentVersion).where(
        DocumentVersion.document_id == document.id,
        DocumentVersion.source_hash == digest,
    ))
    if existing:
        return existing
    last = db.scalar(select(DocumentVersion).where(DocumentVersion.document_id == document.id).order_by(DocumentVersion.number.desc()))
    version = DocumentVersion(document_id=document.id, number=(last.number + 1 if last else 1), source_hash=digest)
    db.add(version); db.flush()
    for item in parsed:
        logical_id = stable_id(document_key, item.identity_path)
        if not db.get(LogicalNode, logical_id):
            db.add(LogicalNode(id=logical_id, document_id=document.id, identity_path=item.identity_path))
        db.add(NodeSnapshot(
            logical_id=logical_id, version_id=version.id,
            parent_logical_id=stable_id(document_key, item.parent.identity_path) if item.parent else None,
            heading=item.heading, level=item.level, body=item.body, full_text=item.full_text,
            content_hash=item.content_hash, position=item.position,
        ))
    db.commit(); db.refresh(version)
    return version

def resolve_version(db: Session, number: int | None, document_key: str = "ct-200") -> DocumentVersion:
    document = db.scalar(select(Document).where(Document.key == document_key))
    if not document:
        raise LookupError("Document not found")
    query = select(DocumentVersion).where(
        DocumentVersion.document_id == document.id
    ).order_by(DocumentVersion.number.desc())
    if number is not None:
        query = select(DocumentVersion).where(
            DocumentVersion.document_id == document.id,
            DocumentVersion.number == number,
        )
    version = db.scalar(query)
    if not version:
        raise LookupError("Document version not found")
    return version

def search_nodes(db: Session, version_id: int, query: str):
    term = f"%{query}%"
    return db.scalars(select(NodeSnapshot).where(
        NodeSnapshot.version_id == version_id,
        or_(NodeSnapshot.heading.ilike(term), NodeSnapshot.body.ilike(term)),
    ).order_by(NodeSnapshot.position)).all()

def compare_node(db: Session, logical_id: str):
    logical = db.get(LogicalNode, logical_id)
    if not logical:
        raise LookupError("Node not found")
    versions = db.scalars(select(DocumentVersion).where(
        DocumentVersion.document_id == logical.document_id
    ).order_by(DocumentVersion.number)).all()
    rows = db.scalars(select(NodeSnapshot).where(NodeSnapshot.logical_id == logical_id).order_by(NodeSnapshot.version_id)).all()
    if not rows:
        raise LookupError("Node not found")
    by_version = {row.version_id: row for row in rows}
    baseline = by_version.get(versions[0].id)
    latest = by_version.get(versions[-1].id)
    if baseline is None:
        status, changed, old_text, new_text = "added", True, "", latest.full_text
    elif latest is None:
        status, changed, old_text, new_text = "removed", True, baseline.full_text, ""
    else:
        changed = latest.content_hash != baseline.content_hash
        status = "changed" if changed else "unchanged"
        old_text, new_text = baseline.full_text, latest.full_text
    ratio = SequenceMatcher(None, old_text, new_text).ratio()
    diff = list(unified_diff(old_text.splitlines(), new_text.splitlines(), lineterm=""))[:20] if changed else []
    return {"logical_id": logical_id, "status": status, "changed": changed,
            "from_version": versions[0].number, "to_version": versions[-1].number,
            "similarity": round(ratio, 3), "diff": diff}

def selection_text(selection: Selection) -> str:
    return "\n\n---\n\n".join(item.snapshot.full_text for item in selection.items)

def document_key_for_snapshot(snapshot: NodeSnapshot) -> str:
    return snapshot.version.document.key
