"""Integration smoke tests for API CRUD, step execution and error history."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import Base, app, session


@pytest.fixture
def client():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    def test_session():
        with factory() as db:
            yield db

    app.dependency_overrides[session] = test_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def payload(kinds, values=None):
    values = values or {}
    nodes = [
        {"id": str(i), "data": {"kind": kind, "label": kind, "value": values.get(i, "")}}
        for i, kind in enumerate(kinds)
    ]
    edges = [{"source": str(i), "target": str(i + 1)} for i in range(len(nodes) - 1)]
    return {"name": "Portfolio demo", "nodes": nodes, "edges": edges}


def test_create_update_execute_delete(client):
    created = client.post("/api/workflows", json=payload(
        ["start", "setText", "uppercase", "end"], {1: "hello world"}
    ))
    assert created.status_code == 201
    wid = created.json()["id"]
    assert client.put(f"/api/workflows/{wid}", json=payload(
        ["start", "setText", "uppercase", "end"], {1: "hello portfolio"}
    )).status_code == 200
    execution = client.post(f"/api/workflows/{wid}/runs")
    assert execution.status_code == 201
    assert execution.json()["status"] == "success"
    assert execution.json()["output"] == "HELLO PORTFOLIO"
    assert len(client.get(f"/api/workflows/{wid}/runs").json()) == 1
    assert client.delete(f"/api/workflows/{wid}").status_code == 204
    assert client.get(f"/api/workflows/{wid}/runs").status_code == 404


def test_failed_http_request_persisted(client):
    created = client.post("/api/workflows", json=payload(
        ["start", "httpGet", "end"], {1: "https://localhost/secret"}
    ))
    wid = created.json()["id"]
    result = client.post(f"/api/workflows/{wid}/runs")
    assert result.status_code == 201
    assert result.json()["status"] == "failed"
    assert "not allowed" in result.json()["steps"][-1]["error"]
    runs = client.get(f"/api/workflows/{wid}/runs").json()
    assert runs[0]["status"] == "failed"
    assert runs[0]["steps"][-1]["status"] == "failed"


def test_invalid_graph_reports_422(client):
    draft = payload(["start", "end"])
    draft["edges"] = []
    wid = client.post("/api/workflows", json=draft).json()["id"]
    result = client.post(f"/api/workflows/{wid}/runs")
    assert result.status_code == 422
    assert "Connect all steps" in result.json()["detail"]
