"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  Handle,
  Position,
  addEdge,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import {
  Activity,
  ArrowRight,
  Check,
  ChevronDown,
  CirclePlay,
  Clock3,
  Code2,
  FileText,
  GitBranch,
  Layers2,
  Plus,
  Save,
  Terminal,
  Trash2,
  Workflow,
  X,
} from "lucide-react";

type Kind = "start" | "setText" | "uppercase" | "append" | "end";
type WorkflowRecord = {
  id: string;
  name: string;
  nodes: Node[];
  edges: Edge[];
  created_at: string;
};
type RunStep = { node_id: string; label: string; input: string; output: string; status: string };
type RunRecord = {
  id: string;
  status: string;
  output: string;
  steps: RunStep[];
  created_at: string;
};

const blocks: { kind: Kind; label: string; details: string }[] = [
  { kind: "start", label: "Start", details: "Trigger a workflow" },
  { kind: "setText", label: "Set text", details: "Define a value" },
  { kind: "uppercase", label: "Uppercase", details: "Transform text" },
  { kind: "append", label: "Append text", details: "Add to a value" },
  { kind: "end", label: "End", details: "Finish execution" },
];

function nodeKind(node: Node): Kind {
  return String(node.data.kind || "start") as Kind;
}

function createNode(kind: Kind, count: number): Node {
  const block = blocks.find((b) => b.kind === kind)!;
  return {
    id: crypto.randomUUID(),
    type: "step",
    position: { x: 110 + count * 34, y: 100 + count * 38 },
    data: { kind, label: block.label, value: "" },
  };
}

function StudioNode({ data, selected }: NodeProps) {
  const kind = String(data.kind || "start");
  const label = String(data.label || "Step");
  const value = String(data.value || "");
  return (
    <div className={"workflow-node kind-" + kind + (selected ? " selected" : "")}>
      {kind !== "start" && <Handle type="target" position={Position.Left} />}
      <div className="node-top"><span className="node-dot" /><span>{label}</span></div>
      <div className="node-description">
        {kind === "setText" || kind === "append" ? (value || "Configure text...") : kind === "start" ? "Entry point" : kind === "end" ? "Workflow complete" : "Transform to uppercase"}
      </div>
      {kind !== "end" && <Handle type="source" position={Position.Right} />}
    </div>
  );
}

const nodeTypes = { step: StudioNode };

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch("/api" + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : "Request failed (" + response.status + ")");
  }
  return response.json() as Promise<T>;
}

export default function Home() {
  const [workflows, setWorkflows] = useState<WorkflowRecord[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [name, setName] = useState("Untitled workflow");
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [run, setRun] = useState<RunRecord | null>(null);
  const [activePanel, setActivePanel] = useState<"config" | "history">("config");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const active = useMemo(() => workflows.find((item) => item.id === activeId), [workflows, activeId]);
  const selected = nodes.find((item) => item.id === selectedId);

  useEffect(() => {
    api<WorkflowRecord[]>("/workflows")
      .then((data) => {
        setWorkflows(data);
        setActiveId(data[0]?.id || null);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    const item = workflows.find((workflow) => workflow.id === activeId);
    if (!item) return;
    setName(item.name);
    setNodes(item.nodes);
    setEdges(item.edges);
    setSelectedId(null);
    setActivePanel("config");
    api<RunRecord[]>("/workflows/" + item.id + "/runs")
      .then((data) => { setRuns(data); setRun(data[0] || null); })
      .catch((e: Error) => setError(e.message));
    // Intentionally only resets the canvas when switching to a different workflow.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId]);

  const onConnect = useCallback(
    (connection: Connection) => {
      if (connection.source === connection.target) return;
      setEdges((current) => addEdge({ ...connection, type: "smoothstep", animated: true }, current));
    },
    [setEdges]
  );

  const save = async (): Promise<WorkflowRecord | null> => {
    if (!activeId) return null;
    const saved = await api<WorkflowRecord>("/workflows/" + activeId, {
      method: "PUT",
      body: JSON.stringify({ name: name.trim() || "Untitled workflow", nodes, edges }),
    });
    setWorkflows((items) => items.map((item) => item.id === saved.id ? saved : item));
    setNotice("Workflow saved");
    return saved;
  };

  const handleSave = async () => {
    setBusy(true); setError(""); setNotice("");
    try { await save(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };

  const handleRun = async () => {
    if (!activeId) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await save();
      const result = await api<RunRecord>("/workflows/" + activeId + "/runs", { method: "POST" });
      setRun(result);
      setRuns((items) => [result, ...items].slice(0, 20));
      setActivePanel("history");
      setNotice("Execution completed");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };

  const createWorkflow = async () => {
    setBusy(true); setError(""); setNotice("");
    try {
      const newNodes = [createNode("start", 0), createNode("end", 1)];
      newNodes[1].position = { x: 430, y: 100 };
      const newEdges = [{ id: "start-to-end", source: newNodes[0].id, target: newNodes[1].id, type: "smoothstep" }];
      const created = await api<WorkflowRecord>("/workflows", {
        method: "POST",
        body: JSON.stringify({ name: "New automation", nodes: newNodes, edges: newEdges }),
      });
      setWorkflows((items) => [created, ...items]);
      setActiveId(created.id);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };

  const updateText = (value: string) => {
    if (!selectedId) return;
    setNodes((items) => items.map((item) => item.id === selectedId
      ? { ...item, data: { ...item.data, value } }
      : item));
  };

  const removeNode = () => {
    if (!selectedId) return;
    setNodes((items) => items.filter((item) => item.id !== selectedId));
    setEdges((items) => items.filter((item) => item.source !== selectedId && item.target !== selectedId));
    setSelectedId(null);
  };

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-icon"><Workflow size={20} /></span><span>automate<span className="brand-strong">flow</span><small>Automation studio</small></span></div>
        <div className="nav-title">WORKSPACE</div>
        <button className="nav-active"><Layers2 size={17} /> Workflows <ChevronDown size={14} className="nav-chevron" /></button>
        <div className="section-heading"><span>YOUR AUTOMATIONS</span><button aria-label="Create workflow" title="Create workflow" onClick={createWorkflow} disabled={busy}><Plus size={16} /></button></div>
        <div className="workflow-list">
          {workflows.map((workflow) => (
            <button key={workflow.id} className={"workflow-item" + (workflow.id === activeId ? " active" : "")} onClick={() => setActiveId(workflow.id)}>
              <Workflow size={16} /><span>{workflow.name}</span>{workflow.id === activeId && <span className="active-dot" />}
            </button>
          ))}
        </div>
        <div className="sidebar-bottom"><span className="status-light" /> Local automation workspace <small>Portfolio MVP · v0.1</small></div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="breadcrumbs"><span>Workflows</span><ArrowRight size={14} /><strong>{active?.name || "Studio"}</strong></div>
          <div className="top-actions"><span className="draft-label"><span className="status-light" /> Ready</span><button className="button secondary" disabled={!activeId || busy} onClick={handleSave}><Save size={16} /> Save</button><button className="button primary" disabled={!activeId || busy} onClick={handleRun}><CirclePlay size={17} /> {busy ? "Working..." : "Run workflow"}</button></div>
        </header>

        {(error || notice) && <div className={"toast " + (error ? "toast-error" : "toast-ok")}><span>{error || notice}</span><button aria-label="Dismiss" onClick={() => { setError(""); setNotice(""); }}><X size={15} /></button></div>}

        <div className="headline"><div><div className="eyebrow"><Activity size={14} /> WORKFLOW EDITOR</div><input aria-label="Workflow name" value={name} maxLength={80} onChange={(event) => setName(event.target.value)} className="workflow-name" /><p>Create workflows with connected steps, then inspect every execution.</p></div><span className="step-count">{nodes.length} steps</span></div>

        <div className="studio">
          <section className="palette">
            <div className="panel-title"><Plus size={16} /> Steps <span>CLICK TO ADD</span></div>
            <p className="panel-hint">Add a block and connect it to another step.</p>
            {blocks.map((block) => (
              <button key={block.kind} className="palette-item" onClick={() => setNodes((items) => [...items, createNode(block.kind, items.length)])}>
                <span className={"palette-icon icon-" + block.kind}>{block.kind === "start" ? <CirclePlay size={17} /> : block.kind === "end" ? <Check size={17} /> : block.kind === "uppercase" ? <Code2 size={17} /> : block.kind === "append" ? <Plus size={17} /> : <FileText size={17} />}</span>
                <span><strong>{block.label}</strong><small>{block.details}</small></span>
                <Plus className="palette-add" size={15} />
              </button>
            ))}
            <div className="palette-foot"><GitBranch size={16} /><span>Linear workflows only in this MVP. Connect Start → actions → End.</span></div>
          </section>

          <section className="canvas">
            <div className="canvas-top"><span><span className="canvas-indicator" /> CANVAS</span><span>Drag to arrange · Scroll to zoom</span></div>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeClick={(_, node) => { setSelectedId(node.id); setActivePanel("config"); }}
              onPaneClick={() => setSelectedId(null)}
              nodeTypes={nodeTypes}
              fitView
              colorMode="dark"
              defaultEdgeOptions={{ type: "smoothstep", style: { stroke: "#7987a1", strokeWidth: 2 } }}
              proOptions={{ hideAttribution: true }}
            >
              <Background color="#232a3a" gap={24} size={1} />
              <Controls showInteractive={false} />
            </ReactFlow>
            <div className="canvas-bottom"><span className="kbd">⌘</span> / Ctrl + scroll to zoom</div>
          </section>

          <aside className="inspector">
            <div className="inspector-tabs"><button className={activePanel === "config" ? "tab-active" : ""} onClick={() => setActivePanel("config")}><Code2 size={15} /> Step</button><button className={activePanel === "history" ? "tab-active" : ""} onClick={() => setActivePanel("history")}><Clock3 size={15} /> Runs</button></div>
            {activePanel === "config" ? selected ? (
              <div className="inspector-content">
                <span className="eyebrow">STEP SETTINGS</span><h3>{String(selected.data.label)}</h3>
                <div className="field"><label>Step type</label><div className="field-readonly">{nodeKind(selected)}</div></div>
                {["setText", "append"].includes(nodeKind(selected)) ? (
                  <div className="field"><label>{nodeKind(selected) === "setText" ? "Text value" : "Text to append"}</label><textarea rows={6} maxLength={4000} placeholder="Enter text..." value={String(selected.data.value || "")} onChange={(event) => updateText(event.target.value)} /><small>This value will be used during execution.</small></div>
                ) : <p className="empty-hint">This step does not require configuration.</p>}
                <button className="delete-button" onClick={removeNode}><Trash2 size={15} /> Delete step</button>
              </div>
            ) : <div className="empty-inspector"><span className="empty-icon"><Layers2 size={25} /></span><h3>Configure steps</h3><p>Select a block on the canvas to edit its settings.</p></div> : (
              <div className="inspector-content runs-panel">
                <span className="eyebrow">EXECUTION HISTORY</span><h3>Recent runs</h3>
                {runs.length === 0 ? <p className="empty-hint">No runs yet. Execute the workflow to see step-by-step results.</p> : (
                  <div className="run-list">{runs.map((item) => (
                    <button key={item.id} className={"run-item " + (run?.id === item.id ? "run-selected" : "")} onClick={() => setRun(item)}>
                      <Check size={14} /><span>{new Date(item.created_at).toLocaleString()}</span><small>Success</small>
                    </button>
                  ))}</div>
                )}
              </div>
            )}
          </aside>
        </div>

        <section className="console">
          <div className="console-heading"><span><Terminal size={17} /> Execution details</span><span>{run ? "RUN " + run.id.slice(0, 8) : "NO RUN SELECTED"}</span></div>
          {run ? <div className="console-content"><div className="console-summary"><span className="success-text"><Check size={15} /> Execution successful</span><span>{run.steps.length} steps</span></div><div className="log-table">{run.steps.map((step, index) => <div className="log-row" key={index}><span className="log-index">{String(index + 1).padStart(2, "0")}</span><span className="log-label">{step.label}</span><span className="log-out">{step.output || "—"}</span><span className="log-ok">✓</span></div>)}</div><div className="final-output"><span>FINAL OUTPUT</span><code>{run.output || "(empty string)"}</code></div></div> : <div className="console-placeholder"><Terminal size={17} /> Run a workflow to inspect the execution trace.</div>}
        </section>
        <footer>AutomateFlow <span>·</span> Built for clarity, designed for automation.</footer>
      </main>
    </div>
  );
}
