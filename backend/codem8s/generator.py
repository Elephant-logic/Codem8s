from __future__ import annotations

import re
from typing import Dict, List, Optional

from .models import ProjectSpec


def slug(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return value[:36] or "generated-app"


def is_job_app(idea: str) -> bool:
    text = idea.lower()
    return any(word in text for word in ["job", "career", "application", "interview", "employer"])


def wants_sqlite(idea: str) -> bool:
    text = idea.lower()
    return any(word in text for word in ["sqlite", "database", "save", "persist", "crm", "note", "job"])


def infer_features(idea: str) -> List[str]:
    text = idea.lower()
    features = ["React frontend", "FastAPI backend"]
    features.append("job tracking workflow" if is_job_app(idea) else "records workflow")
    if "crm" in text or "contact" in text:
        features.append("contacts workflow")
    if "note" in text:
        features.append("notes workflow")
    if "dashboard" in text:
        features.append("dashboard summary")
    if wants_sqlite(idea):
        features.append("SQLite persistence")
    if "login" in text or "account" in text or "user" in text:
        features.append("local profile panel")
    return list(dict.fromkeys(features))


def infer_files(idea: str, stack: str = "react-fastapi") -> Dict[str, str]:
    text = idea.lower()
    files: Dict[str, str] = {
        "backend/main.py": "FastAPI backend with app-specific fields",
        "backend/requirements.txt": "backend dependencies",
        "frontend/package.json": "frontend dependencies",
        "frontend/index.html": "html entry",
        "frontend/src/App.jsx": "main React app",
        "frontend/src/main.jsx": "React entry",
        "frontend/src/styles.css": "styles",
        "README.md": "instructions",
    }
    if wants_sqlite(idea):
        files["backend/store.py"] = "SQLite helper used by backend/main.py"
    if "login" in text or "account" in text or "user" in text:
        files["frontend/src/ProfilePanel.jsx"] = "local profile panel"
    if "dashboard" in text:
        files["frontend/src/Dashboard.jsx"] = "dashboard component"
    return files


def build_spec(idea: str, stack: str = "react-fastapi") -> ProjectSpec:
    clean = " ".join(idea.strip().split())
    name = " ".join(part.capitalize() for part in slug(clean).split("-")[:4])
    return ProjectSpec(app_name=name or "Generated App", goal=clean, stack=stack, features=infer_features(clean), files=infer_files(clean, stack))


def apply_instruction(spec: ProjectSpec, instruction: str) -> ProjectSpec:
    text = " ".join(instruction.strip().split())
    if text:
        spec.change_log.append(text)
    spec.features = list(dict.fromkeys(spec.features + infer_features(text)))
    for path, purpose in infer_files(spec.goal + " " + text, spec.stack).items():
        spec.files.setdefault(path, purpose)
    return spec


def backend_main(spec: ProjectSpec) -> str:
    title = spec.app_name.replace('"', "'")
    goal = spec.goal.replace('"', "'")
    sqlite = "backend/store.py" in spec.files
    if sqlite:
        return '''from __future__ import annotations
from datetime import datetime
from typing import List
from uuid import uuid4
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from store import store

app = FastAPI(title="__TITLE__")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class JobIn(BaseModel):
    company: str = Field(min_length=1)
    role: str = Field(min_length=1)
    status: str = "saved"
    notes: str = ""
    next_action: str = ""

class Job(JobIn):
    id: str
    created_at: str

@app.get("/")
def root():
    return {"app": "__TITLE__", "goal": "__GOAL__", "status": "online"}

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/items", response_model=List[Job])
def list_items():
    return [Job(**row) for row in store.fetch_all("SELECT * FROM jobs ORDER BY created_at DESC")]

@app.post("/items", response_model=Job)
def create_item(item: JobIn):
    record = Job(id=str(uuid4()), created_at=datetime.utcnow().isoformat(), **item.model_dump())
    store.execute(
        "INSERT INTO jobs (id, company, role, status, notes, next_action, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (record.id, record.company, record.role, record.status, record.notes, record.next_action, record.created_at),
    )
    return record

@app.delete("/items/{item_id}")
def delete_item(item_id: str):
    rows = store.fetch_all("SELECT id FROM jobs WHERE id = ?", (item_id,))
    if not rows:
        raise HTTPException(404, "Job not found")
    store.execute("DELETE FROM jobs WHERE id = ?", (item_id,))
    return {"deleted": item_id}
'''.replace("__TITLE__", title).replace("__GOAL__", goal)
    return '''from __future__ import annotations
from datetime import datetime
from typing import Dict, List
from uuid import uuid4
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="__TITLE__")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class RecordIn(BaseModel):
    title: str = Field(min_length=1)
    description: str = ""
    status: str = "active"

class Record(RecordIn):
    id: str
    created_at: str

RECORDS: Dict[str, Record] = {}

@app.get("/")
def root():
    return {"app": "__TITLE__", "goal": "__GOAL__", "status": "online"}

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/items", response_model=List[Record])
def list_items():
    return list(RECORDS.values())

@app.post("/items", response_model=Record)
def create_item(item: RecordIn):
    record = Record(id=str(uuid4()), created_at=datetime.utcnow().isoformat(), **item.model_dump())
    RECORDS[record.id] = record
    return record

@app.delete("/items/{item_id}")
def delete_item(item_id: str):
    if item_id not in RECORDS:
        raise HTTPException(404, "Record not found")
    del RECORDS[item_id]
    return {"deleted": item_id}
'''.replace("__TITLE__", title).replace("__GOAL__", goal)


def store_py() -> str:
    return '''from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Any, Iterable

DB_PATH = Path("app.sqlite3")

class Store:
    def __init__(self, path: Path = DB_PATH):
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.setup()

    def setup(self) -> None:
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                company TEXT NOT NULL,
                role TEXT NOT NULL,
                status TEXT NOT NULL,
                notes TEXT NOT NULL,
                next_action TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        self.connection.commit()

    def fetch_all(self, query: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute(query, tuple(params))
        return [dict(row) for row in cursor.fetchall()]

    def execute(self, query: str, params: Iterable[Any] = ()) -> None:
        self.connection.execute(query, tuple(params))
        self.connection.commit()

store = Store()
'''


def app_jsx(spec: ProjectSpec) -> str:
    name = spec.app_name.replace("'", "\\'")
    goal = spec.goal.replace("'", "\\'")
    has_dashboard = "frontend/src/Dashboard.jsx" in spec.files
    dashboard_import = "import Dashboard from './Dashboard.jsx';" if has_dashboard else ""
    dashboard = "<Dashboard items={items} />" if has_dashboard else ""
    return '''import React, { useEffect, useState } from 'react';
__DASHBOARD_IMPORT__
const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export default function App() {
  const [items, setItems] = useState([]);
  const [company, setCompany] = useState('');
  const [role, setRole] = useState('');
  const [status, setStatus] = useState('saved');
  const [notes, setNotes] = useState('');
  const [nextAction, setNextAction] = useState('');
  const [error, setError] = useState('');

  async function loadItems() {
    try {
      const res = await fetch(API + '/items');
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Load failed');
      setItems(data);
    } catch (err) {
      setError(String(err.message || err));
    }
  }

  async function addItem(event) {
    event.preventDefault();
    if (!company.trim() || !role.trim()) return;
    const res = await fetch(API + '/items', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ company, role, status, notes, next_action: nextAction }),
    });
    const data = await res.json();
    if (res.ok) {
      setItems([data, ...items]);
      setCompany('');
      setRole('');
      setStatus('saved');
      setNotes('');
      setNextAction('');
    } else {
      setError(data.detail || 'Save failed');
    }
  }

  async function removeItem(id) {
    await fetch(API + '/items/' + id, { method: 'DELETE' });
    setItems(items.filter((item) => item.id !== id));
  }

  useEffect(() => { loadItems(); }, []);

  return (
    <main className="app">
      <section className="hero">
        <h1>__NAME__</h1>
        <p>__GOAL__</p>
      </section>
      __DASHBOARD__
      <section className="grid">
        <form className="card" onSubmit={addItem}>
          <h2>Add job</h2>
          <input value={company} onChange={(event) => setCompany(event.target.value)} placeholder="Company" />
          <input value={role} onChange={(event) => setRole(event.target.value)} placeholder="Role" />
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="saved">Saved</option>
            <option value="applied">Applied</option>
            <option value="interview">Interview</option>
            <option value="offer">Offer</option>
            <option value="rejected">Rejected</option>
          </select>
          <input value={nextAction} onChange={(event) => setNextAction(event.target.value)} placeholder="Next action" />
          <textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Notes" />
          <button type="submit">Add job</button>
          {error && <p className="error">{error}</p>}
        </form>
        <section className="card">
          <h2>Jobs</h2>
          {items.map((item) => (
            <article className="item" key={item.id}>
              <div>
                <b>{item.company}</b>
                <p>{item.role} · {item.status}</p>
                <p>{item.notes}</p>
                <small>{item.next_action}</small>
              </div>
              <button onClick={() => removeItem(item.id)}>Delete</button>
            </article>
          ))}
        </section>
      </section>
    </main>
  );
}
'''.replace("__NAME__", name).replace("__GOAL__", goal).replace("__DASHBOARD_IMPORT__", dashboard_import).replace("__DASHBOARD__", dashboard)


def dashboard_jsx() -> str:
    return '''import React from 'react';

export default function Dashboard({ items }) {
  const applied = items.filter((item) => item.status === 'applied').length;
  const interviews = items.filter((item) => item.status === 'interview').length;
  return (
    <section className="card dashboard">
      <h2>Dashboard</h2>
      <div className="chips">
        <span>Total jobs: {items.length}</span>
        <span>Applied: {applied}</span>
        <span>Interviews: {interviews}</span>
      </div>
    </section>
  );
}
'''


def generate_file(path: str, spec: ProjectSpec, use_ai: bool = True, previous_errors: Optional[List[str]] = None) -> str:
    if path == "backend/main.py": return backend_main(spec)
    if path == "backend/requirements.txt": return "fastapi==0.111.0\nuvicorn[standard]==0.30.1\npydantic==2.7.4\n"
    if path == "backend/store.py": return store_py()
    if path == "frontend/package.json": return '{"scripts":{"dev":"vite --host 0.0.0.0","build":"vite build","preview":"vite preview"},"dependencies":{"@vitejs/plugin-react":"latest","vite":"latest","react":"latest","react-dom":"latest"},"devDependencies":{}}'
    if path == "frontend/index.html": return '<div id="root"></div><script type="module" src="/src/main.jsx"></script>'
    if path == "frontend/src/App.jsx": return app_jsx(spec)
    if path == "frontend/src/Dashboard.jsx": return dashboard_jsx()
    if path == "frontend/src/main.jsx": return "import React from 'react';\nimport { createRoot } from 'react-dom/client';\nimport App from './App.jsx';\nimport './styles.css';\ncreateRoot(document.getElementById('root')).render(<App />);\n"
    if path == "frontend/src/styles.css": return "body{margin:0;background:#0b1020;color:#eef2ff;font-family:Inter,system-ui}.app{max-width:1100px;margin:auto;padding:24px}.hero,.card{background:#151b33;border:1px solid #2a335a;border-radius:18px;padding:20px;margin:16px 0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}input,textarea,select{width:100%;box-sizing:border-box;margin:8px 0;padding:12px;border-radius:12px;border:1px solid #33406e;background:#090d1a;color:white}button{background:#6d7cff;color:white;border:0;border-radius:12px;padding:10px 14px}.item{border-bottom:1px solid #273052;padding:10px 0}.chips{display:flex;gap:8px;flex-wrap:wrap}.chips span{background:#25305c;border-radius:999px;padding:7px 10px}.error{color:#ff9f9f}@media(max-width:750px){.grid{grid-template-columns:1fr}}"
    if path == "README.md": return f"# {spec.app_name}\n\n{spec.goal}\n\nRun backend: cd backend && pip install -r requirements.txt && uvicorn main:app --reload --port 8000\n\nRun frontend: cd frontend && npm install && npm run dev\n"
    return f"# Generated file for {path}\nPURPOSE = {spec.files.get(path, 'project file')!r}\n"
