from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

from .models import ProjectSpec
from .settings import get_openai_key, get_openai_model

FEATURE_HINTS = {
    "login": "authentication and user accounts",
    "auth": "authentication and user accounts",
    "dashboard": "dashboard summary cards",
    "game": "interactive game screen",
    "api": "REST API endpoints",
    "database": "persistent storage layer",
    "sqlite": "SQLite storage layer",
    "upload": "file upload workflow",
    "chat": "chat style message interface",
    "shop": "catalog and basket workflow",
    "todo": "task management workflow",
    "notes": "notes CRUD workflow",
    "crm": "contacts and pipeline workflow",
}


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:32] or "generated-app"


def infer_features(idea: str) -> List[str]:
    text = idea.lower()
    features = ["React frontend", "FastAPI backend", "CRUD workflow", "zip export ready"]
    for key, value in FEATURE_HINTS.items():
        if key in text:
            features.append(value)
    return list(dict.fromkeys(features))


def infer_files(idea: str, stack: str = "react-fastapi") -> Dict[str, str]:
    text = idea.lower()
    files: Dict[str, str] = {
        "backend/main.py": f"FastAPI backend for: {idea}",
        "backend/requirements.txt": "Python dependencies for the generated backend",
        "frontend/package.json": "React/Vite package config for the generated frontend",
        "frontend/index.html": "Vite HTML entry point",
        "frontend/src/App.jsx": f"Main React UI for: {idea}",
        "frontend/src/main.jsx": "React entry point",
        "frontend/src/styles.css": "Application styling",
        "README.md": "Setup and usage instructions for the generated project",
    }
    if any(word in text for word in ["database", "sqlite", "save", "history", "notes", "todo", "crm"]):
        files["backend/store.py"] = "SQLite persistence helper"
    if any(word in text for word in ["login", "auth", "account", "user"]):
        files["backend/auth.py"] = "Authentication helper functions"
        files["frontend/src/AuthPanel.jsx"] = "Login and registration UI panel"
    if any(word in text for word in ["upload", "file", "image", "pdf"]):
        files["backend/uploads.py"] = "Upload handling helpers"
        files["frontend/src/UploadPanel.jsx"] = "File upload UI panel"
    if any(word in text for word in ["dashboard", "chart", "analytics", "metrics"]):
        files["frontend/src/Dashboard.jsx"] = "Dashboard cards and summaries"
    return files


def build_spec(idea: str, stack: str = "react-fastapi") -> ProjectSpec:
    clean = " ".join(idea.strip().split())
    name = " ".join(word.capitalize() for word in _slug(clean).split("-")[:4]) or "Generated App"
    return ProjectSpec(app_name=name, goal=clean, stack=stack, features=infer_features(clean), files=infer_files(clean, stack))


def apply_instruction(spec: ProjectSpec, instruction: str) -> ProjectSpec:
    text = " ".join(instruction.strip().split())
    if text:
        spec.change_log.append(text)
    merged_goal = f"{spec.goal}. Change request: {text}"
    spec.features = list(dict.fromkeys(spec.features + infer_features(text)))
    for path, purpose in infer_files(merged_goal, spec.stack).items():
        spec.files.setdefault(path, purpose)
    return spec


def _extract_code_block(text: str) -> str:
    marker = "```"
    if marker not in text:
        return text.strip()
    parts = text.split(marker)
    for part in parts:
        cleaned = part.strip()
        if cleaned.startswith(("python", "javascript", "jsx", "json", "css", "html", "bash", "markdown")):
            first_newline = cleaned.find("\n")
            return cleaned[first_newline + 1:].strip() if first_newline >= 0 else ""
    return parts[1].strip()


def _backend_main(spec: ProjectSpec) -> str:
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

class ItemIn(BaseModel):
    title: str = Field(min_length=1)
    description: str = ""
    status: str = "active"

class Item(ItemIn):
    id: str
    created_at: str

ITEMS: Dict[str, Item] = {{}}

@app.get("/")
def root():
    return {{"app": "{title}", "goal": "{goal}", "status": "online"}}

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

@app.put("/items/{{item_id}}", response_model=Item)
def update_item(item_id: str, item: ItemIn):
    if item_id not in ITEMS:
        raise HTTPException(404, "Item not found")
    record = Item(id=item_id, created_at=ITEMS[item_id].created_at, **item.model_dump())
    ITEMS[item_id] = record
    return record

@app.delete("/items/{{item_id}}")
def delete_item(item_id: str):
    if item_id not in ITEMS:
        raise HTTPException(404, "Item not found")
    del ITEMS[item_id]
    return {{"deleted": item_id}}
'''


def _app_jsx(spec: ProjectSpec) -> str:
    app_name = spec.app_name.replace("'", "\\'")
    goal = spec.goal.replace("'", "\\'")
    features = json.dumps(spec.features)
    return f'''import React, {{ useEffect, useState }} from 'react';

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const FEATURES = {features};

export default function App() {{
  const [items, setItems] = useState([]);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState('');

  async function loadItems() {{
    setError('');
    try {{
      const response = await fetch(API + '/items');
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Could not load items');
      setItems(data);
    }} catch (err) {{
      setError(String(err.message || err));
    }}
  }}

  async function addItem(event) {{
    event.preventDefault();
    if (!title.trim()) return;
    setError('');
    try {{
      const response = await fetch(API + '/items', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ title, description, status: 'active' }}),
      }});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Could not save item');
      setItems((current) => [data, ...current]);
      setTitle('');
      setDescription('');
    }} catch (err) {{
      setError(String(err.message || err));
    }}
  }}

  async function removeItem(id) {{
    await fetch(API + '/items/' + id, {{ method: 'DELETE' }});
    setItems((current) => current.filter((item) => item.id !== id));
  }}

  useEffect(() => {{ loadItems(); }}, []);

  return (
    <main className="app">
      <section className="hero">
        <p className="eyebrow">Generated by Codem8s</p>
        <h1>{app_name}</h1>
        <p>{goal}</p>
      </section>

      <section className="card">
        <h2>Features</h2>
        <div className="chips">
          {{FEATURES.map((feature) => <span key={{feature}}>{{feature}}</span>)}}
        </div>
      </section>

      <section className="grid">
        <form className="card" onSubmit={{addItem}}>
          <h2>Create</h2>
          <input value={{title}} onChange={{(event) => setTitle(event.target.value)}} placeholder="Title" />
          <textarea value={{description}} onChange={{(event) => setDescription(event.target.value)}} placeholder="Description" />
          <button type="submit">Add item</button>
          {{error && <p className="error">{{error}}</p>}}
        </form>

        <section className="card">
          <h2>Items</h2>
          {{items.length === 0 && <p>No items yet.</p>}}
          {{items.map((item) => (
            <article className="item" key={{item.id}}>
              <div>
                <strong>{{item.title}}</strong>
                <p>{{item.description}}</p>
              </div>
              <button onClick={{() => removeItem(item.id)}}>Delete</button>
            </article>
          ))}}
        </section>
      </section>
    </main>
  );
}}
'''


def _styles() -> str:
    return """body{margin:0;background:#0b1020;color:#eef2ff;font-family:Inter,system-ui,Arial}.app{max-width:1100px;margin:auto;padding:24px}.hero,.card{background:#151b33;border:1px solid #2a335a;border-radius:18px;padding:20px;margin:16px 0}.eyebrow{color:#94a3ff;text-transform:uppercase;letter-spacing:.12em;font-size:12px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}input,textarea{width:100%;box-sizing:border-box;margin:8px 0;padding:12px;border-radius:12px;border:1px solid #33406e;background:#090d1a;color:white}textarea{min-height:120px}button{background:#6d7cff;color:white;border:0;border-radius:12px;padding:10px 14px;cursor:pointer}.chips{display:flex;gap:8px;flex-wrap:wrap}.chips span{background:#25305c;border:1px solid #4453a4;border-radius:999px;padding:7px 10px}.item{display:flex;align-items:center;justify-content:space-between;gap:12px;border-bottom:1px solid #273052;padding:10px 0}.item p{margin:.25rem 0;color:#cbd5e1}.error{color:#ff9f9f}@media(max-width:750px){.grid{grid-template-columns:1fr}.app{padding:14px}}"""


def _static_file(path: str, spec: ProjectSpec) -> Optional[str]:
    if path == "backend/main.py":
        return _backend_main(spec)
    if path == "backend/requirements.txt":
        return "fastapi==0.111.0\nuvicorn[standard]==0.30.1\npydantic==2.7.4\n"
    if path == "frontend/package.json":
        return '{"scripts":{"dev":"vite --host 0.0.0.0","build":"vite build","preview":"vite preview"},"dependencies":{"@vitejs/plugin-react":"latest","vite":"latest","react":"latest","react-dom":"latest"},"devDependencies":{}}'
    if path == "frontend/index.html":
        return '<div id="root"></div><script type="module" src="/src/main.jsx"></script>'
    if path == "frontend/src/App.jsx":
        return _app_jsx(spec)
    if path == "frontend/src/main.jsx":
        return "import React from 'react';\nimport { createRoot } from 'react-dom/client';\nimport App from './App.jsx';\nimport './styles.css';\n\ncreateRoot(document.getElementById('root')).render(<App />);\n"
    if path == "frontend/src/styles.css":
        return _styles()
    if path == "README.md":
        return f"# {spec.app_name}\n\n{spec.goal}\n\n## Run backend\n\n```bash\ncd backend\npip install -r requirements.txt\nuvicorn main:app --reload --port 8000\n```\n\n## Run frontend\n\n```bash\ncd frontend\nnpm install\nnpm run dev\n```\n"
    return None


def ai_generate_file(path: str, spec: ProjectSpec, previous_errors: Optional[List[str]] = None) -> Optional[str]:
    api_key = get_openai_key()
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        prompt = f"""
Write one complete file for this generated application.
Application goal: {spec.goal}
Stack: {spec.stack}
Features: {spec.features}
Manifest: {spec.files}
Target file: {path}
Purpose: {spec.files.get(path, 'project file')}
Validation errors to fix: {previous_errors or []}
Return only file content. No placeholders. No TODO. No stubs.
""".strip()
        response = client.chat.completions.create(
            model=get_openai_model(),
            messages=[
                {"role": "system", "content": "You write complete project files. You never use placeholder text."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=4000,
        )
        return _extract_code_block(response.choices[0].message.content or "")
    except Exception as exc:
        return f"# AI generation error for {path}\nERROR = {exc!r}\n"


def generate_file(path: str, spec: ProjectSpec, use_ai: bool = True, previous_errors: Optional[List[str]] = None) -> str:
    static = _static_file(path, spec)
    if static is not None:
        return static
    if use_ai:
        generated = ai_generate_file(path, spec, previous_errors)
        if generated:
            return generated
    purpose = spec.files.get(path, "project file")
    return f"# Generated file for {path}\nPURPOSE = {purpose!r}\n"