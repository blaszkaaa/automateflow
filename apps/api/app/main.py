"""FastAPI endpoints and persistence for the portfolio MVP."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import JSON, DateTime, ForeignKey, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .engine import InvalidWorkflow, execute_workflow


def now() -> datetime:
    return datetime.now(timezone.utc)


db_url = os.getenv("DATABASE_URL", "sqlite:///./automateflow.db")
kwargs = {"connect_args": {"check_same_thread": False}} if db_url.startswith("sqlite") else {}
engine = create_engine(db_url, pool_pre_ping=True, **kwargs)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflows.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    output: Mapped[str] = mapped_column(String(4000), default="")
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WorkflowPayload(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    nodes: list[dict[str, Any]] = Field(max_length=25)
    edges: list[dict[str, Any]] = Field(max_length=30)


def session():
    with SessionLocal() as db:
        yield db


def workflow_dict(item: Workflow):
    return {
        "id": item.id,
        "name": item.name,
        "nodes": item.definition["nodes"],
        "edges": item.definition["edges"],
        "created_at": item.created_at,
    }


def run_dict(item: WorkflowRun):
    return {
        "id": item.id,
        "workflow_id": item.workflow_id,
        "status": item.status,
        "output": item.output,
        "steps": item.steps,
        "created_at": item.created_at,
    }


def example_workflow() -> Workflow:
    kinds = ["start", "setText", "uppercase", "append", "end"]
    names = ["Start", "Set text", "Uppercase", "Append text", "End"]
    nodes = [
        {
            "id": str(index + 1),
            "type": "step",
            "position": {"x": index * 230, "y": 160},
            "data": {
                "kind": kind,
                "label": names[index],
                "value": "AutomateFlow is ready" if kind == "setText"
                         else " - WORKFLOW COMPLETED" if kind == "append" else "",
            },
        }
        for index, kind in enumerate(kinds)
    ]
    edges = [
        {"id": str(index) + "-" + str(index + 1), "source": str(index), "target": str(index + 1)}
        for index in range(1, len(nodes))
    ]
    return Workflow(id=str(uuid4()), name="My first automation", definition={"nodes": nodes, "edges": edges})


app = FastAPI(title="AutomateFlow API", version="0.1.0")


@app.on_event("startup")
def initialize():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(Workflow.id).limit(1)) is None:
            db.add(example_workflow())
            db.commit()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/workflows")
def list_workflows(db: Session = Depends(session)):
    items = db.scalars(select(Workflow).order_by(Workflow.created_at.desc())).all()
    return [workflow_dict(item) for item in items]


@app.post("/api/workflows", status_code=201)
def create_workflow(payload: WorkflowPayload, db: Session = Depends(session)):
    item = Workflow(
        id=str(uuid4()),
        name=payload.name,
        definition={"nodes": payload.nodes, "edges": payload.edges},
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return workflow_dict(item)


@app.put("/api/workflows/{workflow_id}")
def save_workflow(workflow_id: str, payload: WorkflowPayload, db: Session = Depends(session)):
    item = db.get(Workflow, workflow_id)
    if item is None:
        raise HTTPException(404, "Workflow not found")
    item.name = payload.name
    item.definition = {"nodes": payload.nodes, "edges": payload.edges}
    db.commit()
    return workflow_dict(item)


@app.get("/api/workflows/{workflow_id}/runs")
def get_runs(workflow_id: str, db: Session = Depends(session)):
    if db.get(Workflow, workflow_id) is None:
        raise HTTPException(404, "Workflow not found")
    runs = db.scalars(
        select(WorkflowRun)
        .where(WorkflowRun.workflow_id == workflow_id)
        .order_by(WorkflowRun.created_at.desc())
        .limit(20)
    ).all()
    return [run_dict(run) for run in runs]


@app.post("/api/workflows/{workflow_id}/runs", status_code=201)
def execute(workflow_id: str, db: Session = Depends(session)):
    item = db.get(Workflow, workflow_id)
    if item is None:
        raise HTTPException(404, "Workflow not found")
    try:
        result = execute_workflow(item.definition["nodes"], item.definition["edges"])
    except InvalidWorkflow as error:
        raise HTTPException(422, str(error)) from error

    run = WorkflowRun(
        id=str(uuid4()),
        workflow_id=item.id,
        status="success",
        output=result["output"],
        steps=result["steps"],
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run_dict(run)
