from __future__ import annotations

import json
from typing import Optional

from .models import ProjectSpec
from .factory_planner import app_kind, fields_for


def _safe(text: str) -> str:
    return text.replace('"', "'").replace("\n", " ")


def _py_type(field: dict) -> str:
    return "float" if field.get("type") == "number" else "str"


def _py_default(field: dict) -> str:
    if field.get("required"):
        return "Field(min_length=1)"
    if field.get("type") == "number":
        return "0"
    return repr(field.get("default", ""))


def backend_main(spec: ProjectSpec) -> str:
    title = _safe(spec.app_name)
    goal = _safe(spec.goal)
    kind = app_kind(spec.goal)
    fields = fields_for(spec.goal)
    use_sqlite = "backend/store.py" in spec.files
    class_lines = "\n".join(f"    {field['name']}: {_py_type(field)} = {_py_default(field)}" for field in fields)
    cols = ", ".join(["id"] + [field["name"] for field in fields] + ["created_at"])
    placeholders = ", ".join(["?"] * (len(fields) + 2))
    values = ", ".join(["record.id"] + [f"record.{field['name']}" for field in fields] + ["record.created_at"])
    if use_sqlite:
        return f'''from __future__ import annotations
from datetime import datetime
from typing import List
from uuid import uuid4
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from store import store

app = FastAPI(title="{title}")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class ItemIn(BaseModel):
{class_lines}

class Item(ItemIn):
    id: str
    created_at: str

@app.get("/")
def root():
    return {{"app": "{title}", "goal": "{goal}", "kind": "{kind}", "status": "online"}}

@app.get("/health")
def health():
    return {{"ok": True}}

@app.get("/items", response_model=List[Item])
def list_items():
    return [Item(**row) for row in store.fetch_all("SELECT * FROM items ORDER BY created_at DESC")]

@app.post("/items", response_model=Item)
def create_item(item: ItemIn):
    record = Item(id=str(uuid4()), created_at=datetime.utcnow().isoformat(), **item.model_dump())
    store.execute("INSERT INTO items ({cols}) VALUES ({placeholders})", ({values},))
    return record

@app.delete("/items/{{item_id}}")
def delete_item(item_id: str):
    rows = store.fetch_all("SELECT id FROM items WHERE id = ?", (item_id,))
    if not rows:
        raise HTTPException(404, "Item not found")
    store.execute("DELETE FROM items WHERE id = ?", (item_id,))
    return {{"deleted": item_id}}
'''
    return f'''from __future__ import annotations
from datetime import datetime
from typing import Dict, List
from uuid import uuid4
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="{title}")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class ItemIn(BaseModel):
{class_lines}

class Item(ItemIn):
    id: str
    created_at: str

ITEMS: Dict[str, Item] = {{}}

@app.get("/")
def root():
    return {{"app": "{title}", "goal": "{goal}", "kind": "{kind}", "status": "online"}}

@app.get("/health")
def health():
    return {{"ok": True}}

@app.get("/items", response_model=List[Item])
def list_items():
    return list(ITEMS.values())

@app.post("/items", response_model=Item)
def create_item(item: ItemIn):
    record = Item(id=str(uuid4()), created_at=datetime.utcnow().isoformat(), **item.model_dump())
    ITEMS[record.id] = record
    return record

@app.delete("/items/{{item_id}}")
def delete_item(item_id: str):
    if item_id not in ITEMS:
        raise HTTPException(404, "Item not found")
    del ITEMS[item_id]
    return {{"deleted": item_id}}
'''


def store_py(spec: ProjectSpec) -> str:
    lines = []
    for field in fields_for(spec.goal):
        column_type = "REAL" if field.get("type") == "number" else "TEXT"
        default = "NOT NULL DEFAULT 0" if field.get("type") == "number" else "NOT NULL DEFAULT ''"
        if field.get("required"):
            default = "NOT NULL"
        lines.append(f"                {field['name']} {column_type} {default},")
    columns = "\n".join(lines)
    return f'''from __future__ import annotations
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
            CREATE TABLE IF NOT EXISTS items (
                id TEXT PRIMARY KEY,
{columns}
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
    fields_json = json.dumps(fields_for(spec.goal))
    title = spec.app_name.replace("'", "\\'")
    goal = spec.goal.replace("'", "\\'")
    dash_import = "import Dashboard from './components/Dashboard.jsx';" if "frontend/src/components/Dashboard.jsx" in spec.files else ""
    dash_node = "<Dashboard items={items} fields={FIELDS} />" if dash_import else ""
    profile_import = "import ProfilePanel from './components/ProfilePanel.jsx';" if "frontend/src/components/ProfilePanel.jsx" in spec.files else ""
    profile_node = "<ProfilePanel />" if profile_import else ""
    return f'''import React, {{ useEffect, useState }} from 'react';
import DynamicForm from './components/DynamicForm.jsx';
import RecordList from './components/RecordList.jsx';
{dash_import}
{profile_import}

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const FIELDS = {fields_json};

export default function App() {{
  const [items, setItems] = useState([]);
  const [error, setError] = useState('');

  async function loadItems() {{
    try {{
      const res = await fetch(API + '/items');
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Load failed');
      setItems(data);
    }} catch (err) {{
      setError(String(err.message || err));
    }}
  }}

  async function addItem(payload) {{
    const res = await fetch(API + '/items', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify(payload),
    }});
    const data = await res.json();
    if (res.ok) {{
      setItems([data, ...items]);
      setError('');
    }} else {{
      setError(data.detail || 'Save failed');
    }}
  }}

  async function removeItem(id) {{
    await fetch(API + '/items/' + id, {{ method: 'DELETE' }});
    setItems(items.filter((item) => item.id !== id));
  }}

  useEffect(() => {{ loadItems(); }}, []);

  return (
    <main className="app">
      <section className="hero"><h1>{title}</h1><p>{goal}</p></section>
      {profile_node}
      {dash_node}
      <section className="grid">
        <DynamicForm fields={{FIELDS}} onSubmit={{addItem}} error={{error}} />
        <RecordList fields={{FIELDS}} items={{items}} onDelete={{removeItem}} />
      </section>
    </main>
  );
}}
'''


def dynamic_form_jsx() -> str:
    return '''import React, { useMemo, useState } from 'react';

export default function DynamicForm({ fields, onSubmit, error }) {
  const initial = useMemo(() => Object.fromEntries(fields.map((field) => [field.name, field.default ?? ''])), [fields]);
  const [form, setForm] = useState(initial);

  function update(name, value) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  function submit(event) {
    event.preventDefault();
    const missing = fields.some((field) => field.required && !String(form[field.name] || '').trim());
    if (missing) return;
    onSubmit(form);
    setForm(initial);
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2>Create</h2>
      {fields.map((field) => (
        <label key={field.name}>
          <span>{field.label}</span>
          {field.type === 'textarea' ? (
            <textarea value={form[field.name] || ''} onChange={(event) => update(field.name, event.target.value)} />
          ) : field.type === 'select' ? (
            <select value={form[field.name] || field.default || ''} onChange={(event) => update(field.name, event.target.value)}>
              {(field.options || []).map((option) => <option key={option} value={option}>{option}</option>)}
            </select>
          ) : (
            <input type={field.type || 'text'} value={form[field.name] || ''} onChange={(event) => update(field.name, event.target.value)} />
          )}
        </label>
      ))}
      <button type="submit">Save</button>
      {error && <p className="error">{error}</p>}
    </form>
  );
}
'''


def record_list_jsx() -> str:
    return '''import React from 'react';

export default function RecordList({ fields, items, onDelete }) {
  const primary = fields[0]?.name || 'title';
  const secondary = fields[1]?.name;
  return (
    <section className="card">
      <h2>Records</h2>
      {items.length === 0 && <p>No records yet.</p>}
      {items.map((item) => (
        <article className="item" key={item.id}>
          <div>
            <b>{item[primary]}</b>
            {secondary && <p>{item[secondary]}</p>}
            <div className="meta">
              {fields.slice(2).map((field) => item[field.name] ? <span key={field.name}>{field.label}: {item[field.name]}</span> : null)}
            </div>
          </div>
          <button onClick={() => onDelete(item.id)}>Delete</button>
        </article>
      ))}
    </section>
  );
}
'''


def dashboard_jsx() -> str:
    return '''import React from 'react';

export default function Dashboard({ items, fields }) {
  const statusField = fields.find((field) => field.name === 'status');
  const counts = statusField ? Object.fromEntries((statusField.options || []).map((option) => [option, items.filter((item) => item.status === option).length])) : {};
  return (
    <section className="card dashboard">
      <h2>Dashboard</h2>
      <div className="chips">
        <span>Total: {items.length}</span>
        {Object.entries(counts).map(([key, value]) => <span key={key}>{key}: {value}</span>)}
      </div>
    </section>
  );
}
'''


def profile_panel_jsx() -> str:
    return '''import React, { useState } from 'react';

export default function ProfilePanel() {
  const [email, setEmail] = useState('');
  const [saved, setSaved] = useState('');
  function submit(event) {
    event.preventDefault();
    setSaved(email.trim());
  }
  return <form className="card" onSubmit={submit}><h2>Profile</h2><input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Email" /><button>Save profile</button>{saved && <p>Signed in as {saved}</p>}</form>;
}
'''


def styles_css() -> str:
    return "body{margin:0;background:#0b1020;color:#eef2ff;font-family:Inter,system-ui}.app{max-width:1100px;margin:auto;padding:24px}.hero,.card{background:#151b33;border:1px solid #2a335a;border-radius:18px;padding:20px;margin:16px 0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}label{display:block;margin:8px 0}label span{display:block;margin-bottom:4px;color:#cbd5e1}input,textarea,select{width:100%;box-sizing:border-box;margin:0 0 8px;padding:12px;border-radius:12px;border:1px solid #33406e;background:#090d1a;color:white}button{background:#6d7cff;color:white;border:0;border-radius:12px;padding:10px 14px}.item{display:flex;justify-content:space-between;gap:12px;border-bottom:1px solid #273052;padding:10px 0}.meta{display:flex;gap:8px;flex-wrap:wrap}.meta span,.chips span{background:#25305c;border-radius:999px;padding:6px 9px}.chips{display:flex;gap:8px;flex-wrap:wrap}.error{color:#ff9f9f}@media(max-width:750px){.grid{grid-template-columns:1fr}}"


def render_file(path: str, spec: ProjectSpec) -> Optional[str]:
    if path == "backend/main.py": return backend_main(spec)
    if path == "backend/store.py": return store_py(spec)
    if path == "frontend/src/App.jsx": return app_jsx(spec)
    if path == "frontend/src/components/DynamicForm.jsx": return dynamic_form_jsx()
    if path == "frontend/src/components/RecordList.jsx": return record_list_jsx()
    if path == "frontend/src/components/Dashboard.jsx": return dashboard_jsx()
    if path == "frontend/src/components/ProfilePanel.jsx": return profile_panel_jsx()
    if path == "frontend/src/styles.css": return styles_css()
    return None
