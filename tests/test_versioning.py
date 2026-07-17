from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Document, DocumentVersion, NodeSnapshot
from app.services import compare_node, ingest, resolve_version

def test_changed_node_keeps_logical_id(tmp_path: Path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    v1 = tmp_path / "v1.md"; v2 = tmp_path / "v2.md"
    v1.write_text("# Manual\n## Limit\n300 mmHg")
    v2.write_text("# Manual\n## Limit\n295 mmHg")
    one = ingest(db, v1); two = ingest(db, v2)
    first = db.scalar(select(NodeSnapshot).where(NodeSnapshot.version_id == one.id, NodeSnapshot.heading == "Limit"))
    second = db.scalar(select(NodeSnapshot).where(NodeSnapshot.version_id == two.id, NodeSnapshot.heading == "Limit"))
    assert first.logical_id == second.logical_id
    assert first.content_hash != second.content_hash

def test_same_source_can_be_version_one_of_two_documents(tmp_path: Path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    source = tmp_path / "manual.md"
    source.write_text("# Manual\n## Safety\nBe safe")
    first = ingest(db, source, "device-a")
    second = ingest(db, source, "device-b")
    assert first.id != second.id
    assert resolve_version(db, 1, "device-a").document.key == "device-a"
    assert resolve_version(db, 1, "device-b").document.key == "device-b"
    assert len(db.scalars(select(Document)).all()) == 2

def test_reingesting_identical_source_is_idempotent(tmp_path: Path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    source = tmp_path / "manual.md"
    source.write_text("# Manual\n## Safety\nBe safe")
    assert ingest(db, source).id == ingest(db, source).id
    assert len(db.scalars(select(DocumentVersion)).all()) == 1

def test_change_summary_reports_added_and_removed_nodes(tmp_path: Path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    v1 = tmp_path / "v1.md"; v2 = tmp_path / "v2.md"
    v1.write_text("# Manual\n## Removed\nOld")
    v2.write_text("# Manual\n## Added\nNew")
    one = ingest(db, v1); two = ingest(db, v2)
    removed = db.scalar(select(NodeSnapshot).where(NodeSnapshot.version_id == one.id, NodeSnapshot.heading == "Removed"))
    added = db.scalar(select(NodeSnapshot).where(NodeSnapshot.version_id == two.id, NodeSnapshot.heading == "Added"))
    assert compare_node(db, removed.logical_id)["status"] == "removed"
    assert compare_node(db, added.logical_id)["status"] == "added"
