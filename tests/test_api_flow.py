from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import config, generation
from app.database import Base, get_db
from app.main import app


def test_end_to_end_staleness_flow(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    generation.GENERATION_STORE = tmp_path / "generations"
    root = Path(__file__).resolve().parent.parent

    with TestClient(app) as client:
        assert client.get("/", follow_redirects=False).headers["location"] == "/docs"
        assert client.get("/health").json()["status"] == "ok"
        first = client.post("/documents/ingest", json={"path": str(root / "data/ct200_manual.md")})
        assert first.status_code == 200
        duplicate = client.post("/documents/ingest", json={"path": str(root / "data/ct200_manual.md")})
        assert duplicate.json()["version"] == 1
        sections = client.get("/sections", params={"version": 1}).json()["sections"]
        assert len(sections) == 8
        assert sections[0]["heading"] == "1. Intended Use"
        assert any(section["heading"] == "Error reference" for section in sections)
        results = client.get("/search", params={"q": "pressure", "version": 1}).json()["results"]
        source = next(n for n in results if n["heading"] == "Cuff pressure protection")
        node = client.get(f"/nodes/{source['parent_id']}", params={"version": 1})
        assert any(child["id"] == source["id"] for child in node.json()["children"])
        missing_selection = client.post("/selections", json={
            "name": "Invalid", "version": 1, "node_ids": ["not-a-real-node"]
        })
        assert missing_selection.status_code == 400
        selection = client.post("/selections", json={
            "name": "Pressure safety v1", "version": 1, "node_ids": [source["id"]]
        })
        assert selection.status_code == 201
        selection_id = selection.json()["id"]
        generated = client.post(f"/selections/{selection_id}/generate", json={})
        assert generated.status_code == 200
        assert len(generated.json()["test_cases"]) == 3
        reused = client.post(f"/selections/{selection_id}/generate", json={})
        assert reused.json()["reused"] is True

        second = client.post("/documents/ingest", json={"path": str(root / "data/ct200_manual_v2.md")})
        assert second.status_code == 200
        retrieved = client.get(f"/generations/selection/{selection_id}")
        assert retrieved.status_code == 200
        assert retrieved.json()["stale"] is True
        assert retrieved.json()["impact"][0]["status"] == "stale"
        change = client.get(f"/nodes/{source['id']}/changes").json()
        assert change["changed"] is True
        assert any("300 mmHg" in line for line in change["diff"])
        by_node = client.get(f"/generations/node/{source['id']}").json()
        assert len(by_node["generations"]) == 1

    app.dependency_overrides.clear()
