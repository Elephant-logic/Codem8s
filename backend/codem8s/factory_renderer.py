from __future__ import annotations
import json
from typing import Optional
from .models import ProjectSpec
from .agent_blueprint import blueprint_from_spec

def render_file(path: str, spec: ProjectSpec) -> Optional[str]:
    bp = blueprint_from_spec(spec)
    if bp.get("kind") == "game" or bp.get("needs_backend") is False:
        return render_game_file(path, bp)
    if path == "backend/main.py": return backend_main(bp)
    if path == "backend/store.py": return store_py(bp)
    if path == "frontend/src/App.jsx": return app_jsx(bp)
    if path == "frontend/src/components/Nav.jsx": return nav_jsx()
    if path == "frontend/src/components/Dashboard.jsx": return dashboard_jsx()
    if path == "frontend/src/components/EntityPage.jsx": return entity_page_jsx()
    if path == "frontend/src/components/FormBuilder.jsx": return form_builder_jsx()
    if path == "frontend/src/styles.css": return styles_css()
    return None

def py_type(field: dict) -> str:
    return "float" if field.get("type") == "number" else "str"

def py_default(field: dict) -> str:
    if field.get("required"): return "Field(min_length=1)"
    if field.get("type") == "number": return "0"
    opts = field.get("options") or []
    return repr(opts[0] if opts else "")

def cls_name(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_"))

def backend_main(bp: dict) -> str:
    models, routes = [], []
    for ent in bp.get("entities", []):
        name, cls = ent["name"], cls_name(ent["name"])
        field_lines = "\n".join(f"    {f['name']}: {py_type(f)} = {py_default(f)}" for f in ent.get("fields", []))
        cols = ", ".join(["id"] + [f["name"] for f in ent.get("fields", [])] + ["created_at"])
        placeholders = ", ".join(["?"] * (len(ent.get("fields", [])) + 2))
        values = ", ".join(["record.id"] + [f"record.{f['name']}" for f in ent.get("fields", [])] + ["record.created_at"])
        models.append(f"class {cls}In(BaseModel):\n{field_lines}\n\nclass {cls}({cls}In):\n    id: str\n    created_at: str\n")
        routes.append(f'''@app.get("/{name}", response_model=List[{cls}])
def list_{name}():
    return [{cls}(**row) for row in store.fetch_all("SELECT * FROM {name} ORDER BY created_at DESC")]

@app.post("/{name}", response_model={cls})
def create_{name}(item: {cls}In):
    record = {cls}(id=str(uuid4()), created_at=datetime.utcnow().isoformat(), **item.model_dump())
    store.execute("INSERT INTO {name} ({cols}) VALUES ({placeholders})", ({values},))
    return record

@app.delete("/{name}/{{item_id}}")
def delete_{name}(item_id: str):
    store.execute("DELETE FROM {name} WHERE id = ?", (item_id,))
    return {{"deleted": item_id}}
''')
    blueprint = json.dumps({"kind": bp.get("kind"), "pages": bp.get("pages"), "entities": bp.get("entities")})
    return f'''from __future__ import annotations
from datetime import datetime
from typing import List
from uuid import uuid4
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from store import store

app = FastAPI(title={bp.get("app_name", "Generated App")!r})
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

{chr(10).join(models)}

@app.get("/")
def root():
    return {{"app": {bp.get("app_name", "Generated App")!r}, "kind": {bp.get("kind", "business_app")!r}, "status": "online"}}

@app.get("/blueprint")
def blueprint():
    return {blueprint}

{chr(10).join(routes)}
'''

def store_py(bp: dict) -> str:
    table_code = []
    for ent in bp.get("entities", []):
        cols = []
        for f in ent.get("fields", []):
            typ = "REAL" if f.get("type") == "number" else "TEXT"
            default = "NOT NULL" if f.get("required") else ("NOT NULL DEFAULT 0" if typ == "REAL" else "NOT NULL DEFAULT ''")
            cols.append(f"{f['name']} {typ} {default}")
        columns = ", ".join(["id TEXT PRIMARY KEY"] + cols + ["created_at TEXT NOT NULL"])
        table_code.append(f'        self.connection.execute("CREATE TABLE IF NOT EXISTS {ent["name"]} ({columns})")')
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
{chr(10).join(table_code)}
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

def app_jsx(bp: dict) -> str:
    pages = json.dumps([p["name"] for p in bp.get("pages", [])])
    entities = json.dumps(bp.get("entities", []))
    return f'''import React, {{ useEffect, useState }} from 'react';
import Nav from './components/Nav.jsx';
import Dashboard from './components/Dashboard.jsx';
import EntityPage from './components/EntityPage.jsx';

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const PAGES = {pages};
const ENTITIES = {entities};

export default function App() {{
  const [page, setPage] = useState(PAGES[0] || 'Dashboard');
  const [data, setData] = useState({{}});

  async function load(entity) {{
    const res = await fetch(API + '/' + entity.name);
    const json = await res.json();
    setData((old) => ({{ ...old, [entity.name]: json }}));
  }}

  useEffect(() => {{ ENTITIES.forEach(load); }}, []);

  async function create(entity, payload) {{
    const res = await fetch(API + '/' + entity.name, {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(payload) }});
    if (res.ok) load(entity);
  }}

  async function remove(entity, id) {{
    await fetch(API + '/' + entity.name + '/' + id, {{ method: 'DELETE' }});
    load(entity);
  }}

  const entity = ENTITIES.find((e) => page.toLowerCase().includes(e.name.toLowerCase().replace(/s$/, ''))) || ENTITIES[0];

  return (
    <main className="app">
      <header className="hero"><h1>{bp.get("app_name", "Generated App")}</h1><p>{bp.get("goal", "")}</p></header>
      <Nav pages={{PAGES}} active={{page}} onChange={{setPage}} />
      {{page === 'Dashboard' ? <Dashboard entities={{ENTITIES}} data={{data}} /> : <EntityPage page={{page}} entity={{entity}} rows={{data[entity?.name] || []}} onCreate={{create}} onDelete={{remove}} />}}
    </main>
  );
}}
'''

def nav_jsx() -> str:
    return '''import React from 'react';
export default function Nav({ pages, active, onChange }) {
  return <nav className="tabs">{pages.map((page) => <button key={page} className={page === active ? 'active' : ''} onClick={() => onChange(page)}>{page}</button>)}</nav>;
}
'''

def dashboard_jsx() -> str:
    return '''import React from 'react';
export default function Dashboard({ entities, data }) {
  return <section className="grid">{entities.map((entity) => <article className="card" key={entity.name}><h2>{entity.label || entity.name}</h2><p>{(data[entity.name] || []).length} records</p></article>)}</section>;
}
'''

def form_builder_jsx() -> str:
    return '''import React, { useMemo, useState } from 'react';
export default function FormBuilder({ entity, onSubmit }) {
  const initial = useMemo(() => Object.fromEntries((entity?.fields || []).map((f) => [f.name, f.options?.[0] || ''])), [entity]);
  const [form, setForm] = useState(initial);
  function submit(event) { event.preventDefault(); onSubmit(entity, form); setForm(initial); }
  return <form className="card" onSubmit={submit}><h2>Add {entity?.label || entity?.name}</h2>{(entity?.fields || []).map((f) => <label key={f.name}><span>{f.label}</span>{f.type === 'textarea' ? <textarea value={form[f.name] || ''} onChange={(e) => setForm({...form, [f.name]: e.target.value})} /> : f.type === 'select' ? <select value={form[f.name] || f.options?.[0] || ''} onChange={(e) => setForm({...form, [f.name]: e.target.value})}>{(f.options || []).map((o) => <option key={o}>{o}</option>)}</select> : <input type={f.type || 'text'} value={form[f.name] || ''} onChange={(e) => setForm({...form, [f.name]: e.target.value})} />}</label>)}<button>Save</button></form>;
}
'''

def entity_page_jsx() -> str:
    return '''import React from 'react';
import FormBuilder from './FormBuilder.jsx';
export default function EntityPage({ page, entity, rows, onCreate, onDelete }) {
  if (!entity) return <section className="card"><h2>{page}</h2><p>No entity generated for this page.</p></section>;
  const primary = entity.fields?.[0]?.name || 'id';
  return <section className="grid"><FormBuilder entity={entity} onSubmit={onCreate} /><section className="card"><h2>{page}</h2>{rows.map((row) => <article className="item" key={row.id}><div><b>{row[primary]}</b><div className="meta">{entity.fields.slice(1).map((f) => row[f.name] ? <span key={f.name}>{f.label}: {row[f.name]}</span> : null)}</div></div><button onClick={() => onDelete(entity, row.id)}>Delete</button></article>)}</section></section>;
}
'''

def styles_css() -> str:
    return "body{margin:0;background:#0b1020;color:#eef2ff;font-family:Inter,system-ui}.app{max-width:1150px;margin:auto;padding:24px}.hero,.card{background:#151b33;border:1px solid #2a335a;border-radius:18px;padding:20px;margin:16px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}.tabs{display:flex;gap:8px;flex-wrap:wrap}.tabs .active{outline:2px solid #fff}button{background:#6d7cff;color:white;border:0;border-radius:12px;padding:10px 14px}label{display:block;margin:8px 0}label span{display:block;color:#cbd5e1;margin-bottom:4px}input,textarea,select{width:100%;box-sizing:border-box;padding:12px;border-radius:12px;border:1px solid #33406e;background:#090d1a;color:white}.item{display:flex;justify-content:space-between;gap:12px;border-bottom:1px solid #273052;padding:10px 0}.meta{display:flex;gap:8px;flex-wrap:wrap}.meta span{background:#25305c;border-radius:999px;padding:6px 9px}"

def render_game_file(path: str, bp: dict) -> Optional[str]:
    if path == "frontend/src/App.jsx":
        return f'''import React from 'react';
import GameCanvas from './game/GameCanvas.jsx';
export default function App() {{
  return <main className="app"><header className="hero"><h1>{bp.get("app_name", "Generated Game")}</h1><p>{bp.get("goal", "")}</p></header><GameCanvas /></main>;
}}
'''
    if path == "frontend/src/game/GameCanvas.jsx":
        return '''import React, { useRef } from 'react';
import useGameLoop from './useGameLoop.js';
import { keys } from './input.js';
export default function GameCanvas() {
  const ref = useRef(null);
  useGameLoop(ref);
  return <section className="card"><h2>Game</h2><canvas ref={ref} width="640" height="360" tabIndex="0" onKeyDown={keys.down} onKeyUp={keys.up}></canvas><p>Use arrows or WASD.</p></section>;
}
'''
    if path == "frontend/src/game/useGameLoop.js":
        return '''import { useEffect } from 'react';
import { keys } from './input.js';
import { hitWalls } from './collision.js';
export default function useGameLoop(ref) {
  useEffect(() => {
    const player = { x: 50, y: 50, size: 24, speed: 3 };
    const loop = () => {
      const canvas = ref.current; if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (keys.state.ArrowLeft || keys.state.a) player.x -= player.speed;
      if (keys.state.ArrowRight || keys.state.d) player.x += player.speed;
      if (keys.state.ArrowUp || keys.state.w) player.y -= player.speed;
      if (keys.state.ArrowDown || keys.state.s) player.y += player.speed;
      hitWalls(player, canvas);
      ctx.clearRect(0,0,canvas.width,canvas.height);
      ctx.fillStyle = '#6d7cff'; ctx.fillRect(player.x, player.y, player.size, player.size);
      requestAnimationFrame(loop);
    };
    loop();
  }, [ref]);
}
'''
    if path == "frontend/src/game/input.js":
        return "export const keys = { state: {}, down: (e) => { keys.state[e.key] = true; }, up: (e) => { keys.state[e.key] = false; } };\n"
    if path == "frontend/src/game/collision.js":
        return "export function hitWalls(p, canvas) { p.x = Math.max(0, Math.min(canvas.width - p.size, p.x)); p.y = Math.max(0, Math.min(canvas.height - p.size, p.y)); }\n"
    if path == "frontend/src/styles.css":
        return styles_css() + "canvas{width:100%;background:#090d1a;border:1px solid #33406e;border-radius:16px;outline:none}"
    return None
