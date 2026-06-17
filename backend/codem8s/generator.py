from __future__ import annotations

import re
from typing import Dict, List, Optional

from .models import ProjectSpec


def slug(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return value[:36] or "generated-app"


def infer_features(idea: str) -> List[str]:
    text = idea.lower()
    features = ["React frontend", "FastAPI backend", "records workflow"]
    if "crm" in text or "contact" in text:
        features.append("contacts workflow")
    if "note" in text:
        features.append("notes workflow")
    if "dashboard" in text:
        features.append("dashboard summary")
    if "sqlite" in text or "database" in text:
        features.append("database helper")
    if "login" in text or "account" in text or "user" in text:
        features.append("local profile panel")
    return list(dict.fromkeys(features))


def infer_files(idea: str, stack: str = "react-fastapi") -> Dict[str, str]:
    text = idea.lower()
    files: Dict[str, str] = {
        "backend/main.py": "FastAPI backend",
        "backend/requirements.txt": "backend dependencies",
        "frontend/package.json": "frontend dependencies",
        "frontend/index.html": "html entry",
        "frontend/src/App.jsx": "main React app",
        "frontend/src/main.jsx": "React entry",
        "frontend/src/styles.css": "styles",
        "README.md": "instructions",
    }
    if "sqlite" in text or "database" in text or "crm" in text or "note" in text:
        files["backend/store.py"] = "optional database helper"
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
    return f'''from __future__ import annotations
from datetime import datetime
from typing import Dict, List
from uuid import uuid4
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="{title}")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class RecordIn(BaseModel):
    title: str = Field(min_length=1)
    description: str = ""
    status: str = "active"

class Record(RecordIn):
    id: str
    created_at: str

RECORDS: Dict[str, Record] = {{}}

@app.get("/")
def root():
    return {{"app": "{title}", "goal": "{goal}", "status": "online"}}

@app.get("/health")
def health():
    return {{"ok": True}}

@app.get("/items", response_model=List[Record])
def list_items():
    return list(RECORDS.values())

@app.post("/items", response_model=Record)
def create_item(item: RecordIn):
    record = Record(id=str(uuid4()), created_at=datetime.utcnow().isoformat(), **item.model_dump())
    RECORDS[record.id] = record
    return record

@app.delete("/items/{{item_id}}")
def delete_item(item_id: str):
    if item_id not in RECORDS:
        raise HTTPException(404, "Record not found")
    del RECORDS[item_id]
    return {{"deleted": item_id}}
'''


def app_jsx(spec: ProjectSpec) -> str:
    name = spec.app_name.replace("'", "\\'")
    goal = spec.goal.replace("'", "\\'")
    has_profile = "frontend/src/ProfilePanel.jsx" in spec.files
    has_dashboard = "frontend/src/Dashboard.jsx" in spec.files
    imports = []
    if has_profile:
        imports.append("import ProfilePanel from './ProfilePanel.jsx';")
    if has_dashboard:
        imports.append("import Dashboard from './Dashboard.jsx';")
    profile = "{profile ? <p className='notice'>Profile: {profile.email}</p> : <ProfilePanel onSave={setProfile} />}" if has_profile else ""
    dashboard = "<Dashboard items={items} />" if has_dashboard else ""
    return f'''import React, {{ useEffect, useState }} from 'react';
{"\n".join(imports)}
const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export default function App() {{
  const [items, setItems] = useState([]);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState('');

  async function loadItems() {{
    try {{
      const res = await fetch(API + '/items');
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Load failed');
      setItems(data);
    }} catch (err) {{ setError(String(err.message || err)); }}
  }}

  async function addItem(event) {{
    event.preventDefault();
    if (!title.trim()) return;
    const res = await fetch(API + '/items', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ title, description, status: 'active' }}) }});
    const data = await res.json();
    if (res.ok) {{ setItems([data, ...items]); setTitle(''); setDescription(''); }}
  }}

  async function removeItem(id) {{
    await fetch(API + '/items/' + id, {{ method: 'DELETE' }});
    setItems(items.filter((item) => item.id !== id));
  }}

  useEffect(() => {{ loadItems(); }}, []);

  return <main className="app"><section className="hero"><h1>{name}</h1><p>{goal}</p></section>{profile}{dashboard}<section className="grid"><form className="card" onSubmit={{addItem}}><h2>Create record</h2><input value={{title}} onChange={{(e)=>setTitle(e.target.value)}} placeholder="Title"/><textarea value={{description}} onChange={{(e)=>setDescription(e.target.value)}} placeholder="Description"/><button>Add</button>{{error && <p className="error">{{error}}</p>}}</form><section className="card"><h2>Records</h2>{{items.map((item)=><article className="item" key={{item.id}}><div><b>{{item.title}}</b><p>{{item.description}}</p></div><button onClick={{()=>removeItem(item.id)}}>Delete</button></article>)}}</section></section></main>;
}}
'''


def generate_file(path: str, spec: ProjectSpec, use_ai: bool = True, previous_errors: Optional[List[str]] = None) -> str:
    if path == "backend/main.py": return backend_main(spec)
    if path == "backend/requirements.txt": return "fastapi==0.111.0\nuvicorn[standard]==0.30.1\npydantic==2.7.4\n"
    if path == "backend/store.py": return "from __future__ import annotations\nimport sqlite3\nconnection = sqlite3.connect('app.sqlite3', check_same_thread=False)\n"
    if path == "frontend/package.json": return '{"scripts":{"dev":"vite --host 0.0.0.0","build":"vite build","preview":"vite preview"},"dependencies":{"@vitejs/plugin-react":"latest","vite":"latest","react":"latest","react-dom":"latest"},"devDependencies":{}}'
    if path == "frontend/index.html": return '<div id="root"></div><script type="module" src="/src/main.jsx"></script>'
    if path == "frontend/src/App.jsx": return app_jsx(spec)
    if path == "frontend/src/ProfilePanel.jsx": return "import React,{useState}from'react';export default function ProfilePanel({onSave}){const[email,setEmail]=useState('');function submit(e){e.preventDefault();if(email.trim())onSave({email:email.trim()});}return <form className='card' onSubmit={submit}><h2>Profile</h2><input value={email} onChange={(e)=>setEmail(e.target.value)} placeholder='Email'/><button>Continue</button></form>; }\n"
    if path == "frontend/src/Dashboard.jsx": return "import React from'react';export default function Dashboard({items}){return <section className='card'><h2>Dashboard</h2><p>Total records: {items.length}</p></section>; }\n"
    if path == "frontend/src/main.jsx": return "import React from 'react';\nimport { createRoot } from 'react-dom/client';\nimport App from './App.jsx';\nimport './styles.css';\ncreateRoot(document.getElementById('root')).render(<App />);\n"
    if path == "frontend/src/styles.css": return "body{margin:0;background:#0b1020;color:#eef2ff;font-family:Inter,system-ui}.app{max-width:1100px;margin:auto;padding:24px}.hero,.card{background:#151b33;border:1px solid #2a335a;border-radius:18px;padding:20px;margin:16px 0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}input,textarea{width:100%;box-sizing:border-box;margin:8px 0;padding:12px;border-radius:12px;border:1px solid #33406e;background:#090d1a;color:white}button{background:#6d7cff;color:white;border:0;border-radius:12px;padding:10px 14px}.item{border-bottom:1px solid #273052;padding:10px 0}.error{color:#ff9f9f}@media(max-width:750px){.grid{grid-template-columns:1fr}}"
    if path == "README.md": return f"# {spec.app_name}\n\n{spec.goal}\n\nRun backend: cd backend && pip install -r requirements.txt && uvicorn main:app --reload --port 8000\n\nRun frontend: cd frontend && npm install && npm run dev\n"
    return f"# Generated file for {path}\nPURPOSE = {spec.files.get(path, 'project file')!r}\n"
