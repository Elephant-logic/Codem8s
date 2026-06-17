from __future__ import annotations
from typing import Dict, List
from pathlib import Path
from .models import ProjectSpec
from .settings import get_openai_key, get_openai_model

BASE_FILES: Dict[str, str] = {
    "backend/main.py": "FastAPI app exposing project, change, validate, export endpoints",
    "backend/generator.py": "spec builder and deterministic file generator",
    "backend/validator.py": "strict file and project validator",
    "backend/runner.py": "syntax and smoke-test runner",
    "backend/settings.py": "local settings and stored API key management",
    "backend/exporter.py": "zip export utility",
    "frontend/package.json": "React package config",
    "frontend/src/App.jsx": "live steering user interface",
    "frontend/src/main.jsx": "React entry point",
    "frontend/src/styles.css": "application styling",
    "README.md": "setup and usage instructions",
}

FEATURE_HINTS = {
    "login": "authentication screens and protected routes",
    "dashboard": "dashboard cards, charts, and saved runs",
    "game": "interactive canvas or game loop",
    "api": "REST API endpoints and typed schemas",
    "database": "SQLite persistence layer",
    "upload": "file upload and inspection workflow",
    "export": "zip export and project download",
    "chat": "streaming chat panel and message history",
}

def infer_features(idea: str) -> List[str]:
    text = idea.lower()
    features = ["locked project spec", "file-by-file build", "live change instructions", "strict validation", "zip export"]
    for key, value in FEATURE_HINTS.items():
        if key in text:
            features.append(value)
    return list(dict.fromkeys(features))

def build_spec(idea: str, stack: str = "react-fastapi") -> ProjectSpec:
    clean = " ".join(idea.strip().split())
    name = "Codem8s Project" if len(clean) < 40 else clean[:40].rstrip()
    if "codem8" in clean.lower():
        name = "Codem8s"
    return ProjectSpec(
        app_name=name,
        goal=clean,
        stack=stack,
        features=infer_features(clean),
        files=BASE_FILES.copy(),
    )

def apply_instruction(spec: ProjectSpec, instruction: str) -> ProjectSpec:
    text = " ".join(instruction.strip().split())
    spec.change_log.append(text)
    lowered = text.lower()
    if any(word in lowered for word in ["login", "auth", "user account"]):
        spec.features.append("authentication flow")
        spec.files["frontend/src/auth.jsx"] = "authentication panel"
        spec.files["backend/auth.py"] = "token issuing and verification helpers"
    if any(word in lowered for word in ["sqlite", "database", "save history"]):
        spec.features.append("SQLite project history")
        spec.files["backend/store.py"] = "SQLite storage for projects and generated files"
    if any(word in lowered for word in ["test", "pytest"]):
        spec.features.append("test suite")
        spec.files["backend/tests/test_validator.py"] = "validator unit tests"
    spec.features = list(dict.fromkeys(spec.features))
    return spec


def _extract_code_block(text: str) -> str:
    marker = "```"
    if marker not in text:
        return text.strip()
    parts = text.split(marker)
    for part in parts:
        cleaned = part.strip()
        if cleaned.startswith("python"):
            return cleaned[6:].strip()
        if cleaned.startswith(("javascript", "jsx", "json", "css", "html", "bash", "markdown")):
            first_newline = cleaned.find("\n")
            return cleaned[first_newline + 1:].strip() if first_newline >= 0 else ""
    return parts[1].strip()


def ai_generate_file(path: str, spec: ProjectSpec) -> str | None:
    api_key = get_openai_key()
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        prompt = f"""
You are Codem8s, a strict full-stack code builder.
Write exactly one complete production-quality file.

Locked app spec:
app_name: {spec.app_name}
goal: {spec.goal}
stack: {spec.stack}
features: {spec.features}
manifest: {spec.files}

Target file: {path}
Purpose: {spec.files.get(path, 'project file')}

Rules:
- Return only the file content, preferably in one code block.
- No placeholders, no TODOs, no stubs, no NotImplementedError, no fake functions.
- The file must match the locked spec and target path.
- Keep dependencies sensible and listed in package/requirements files when relevant.
- For Python files, code must parse.
""".strip()
        response = client.chat.completions.create(
            model=get_openai_model(),
            messages=[
                {"role": "system", "content": "You write complete, runnable files and never use placeholders."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=4000,
        )
        return _extract_code_block(response.choices[0].message.content or "")
    except Exception as exc:
        return f"# AI generation failed for {path}\nERROR = {exc!r}\n"

def generate_file(path: str, spec: ProjectSpec, use_ai: bool = True) -> str:
    if use_ai:
        generated = ai_generate_file(path, spec)
        if generated:
            return generated
    if path == "README.md":
        return f"""# {spec.app_name}\n\n{spec.goal}\n\n## Stack\n\n{spec.stack}\n\n## Run\n\nBackend:\n\n```bash\ncd backend\npython -m venv .venv\n. .venv/bin/activate\npip install -r requirements.txt\nuvicorn codem8s.main:app --reload --port 8000\n```\n\nFrontend:\n\n```bash\ncd frontend\nnpm install\nnpm run dev\n```\n\n## Build loop\n\nCreate a locked spec, generate one file at a time, reject banned content, run checks, accept live instructions, then export a zip.\n"""
    if path == "frontend/package.json":
        return '{"scripts":{"dev":"vite --host 0.0.0.0"},"dependencies":{"@vitejs/plugin-react":"latest","vite":"latest","react":"latest","react-dom":"latest","lucide-react":"latest"},"devDependencies":{}}'
    if path == "frontend/src/main.jsx":
        return "import React from 'react';\nimport { createRoot } from 'react-dom/client';\nimport App from './App.jsx';\nimport './styles.css';\n\ncreateRoot(document.getElementById('root')).render(<App />);\n"
    if path == "frontend/src/styles.css":
        return "body{margin:0;background:#0b1020;color:#e8ecff;font-family:Inter,system-ui,Arial}.app{padding:24px;max-width:1200px;margin:auto}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.card{background:#151b33;border:1px solid #2a335a;border-radius:16px;padding:16px}textarea{width:100%;min-height:120px;background:#090d1a;color:#fff;border:1px solid #33406e;border-radius:10px;padding:10px}button{background:#6d7cff;color:white;border:0;border-radius:10px;padding:10px 14px;margin:4px;cursor:pointer}.log{white-space:pre-wrap;font-family:ui-monospace,monospace;font-size:13px}.file{padding:6px;border-bottom:1px solid #273052}.bad{color:#ff9f9f}.ok{color:#93f5b5}"
    if path == "frontend/src/App.jsx":
        return """import React,{useState}from'react';\nconst API='http://localhost:8000';\nexport default function App(){const[idea,setIdea]=useState('Build Codem8s as a full-stack AI code factory');const[change,setChange]=useState('');const[state,setState]=useState(null);const[busy,setBusy]=useState(false);async function post(url,body){setBusy(true);try{const r=await fetch(API+url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});setState(await r.json())}finally{setBusy(false)}}async function create(){await post('/projects',{idea})}async function build(){if(state)await post(`/projects/${state.project_id}/build-next`,{})}async function steer(){if(state&&change.trim()){await post(`/projects/${state.project_id}/change`,{instruction:change});setChange('')}}async function validate(){if(state)await post(`/projects/${state.project_id}/validate`,{})}function download(){if(state)window.location=API+`/projects/${state.project_id}/export`}return <main className='app'><h1>Codem8s Full Stack</h1><p>Locked spec. File-by-file build. Live steering. No fake code saved.</p><div className='grid'><section className='card'><h2>Idea</h2><textarea value={idea} onChange={e=>setIdea(e.target.value)}/><button onClick={create} disabled={busy}>Create Spec</button><button onClick={build} disabled={!state||busy}>Build Next File</button><button onClick={validate} disabled={!state||busy}>Validate</button><button onClick={download} disabled={!state}>Export Zip</button><h2>Steer While Building</h2><textarea value={change} onChange={e=>setChange(e.target.value)} placeholder='Add login, switch to SQLite, make it mobile first'/><button onClick={steer} disabled={!state||busy}>Apply Instruction</button></section><section className='card'><h2>Spec</h2><pre className='log'>{state?JSON.stringify(state.spec,null,2):'No project yet'}</pre></section></div><section className='card'><h2>Files</h2>{state&&Object.values(state.files).map(f=><div className='file' key={f.path}><b>{f.path}</b> <span className={f.status==='valid'?'ok':'bad'}>{f.status}</span>{f.errors?.length>0&&<pre className='bad'>{f.errors.join('\\n')}</pre>}</div>)}</section><section className='card'><h2>Logs</h2><pre className='log'>{state?.logs?.join('\\n')||''}</pre></section></main>}\n"""
    if path == "backend/main.py":
        return """from __future__ import annotations\nfrom fastapi import FastAPI, HTTPException\nfrom fastapi.middleware.cors import CORSMiddleware\nfrom fastapi.responses import FileResponse\nfrom uuid import uuid4\nfrom .models import BuildRequest, ChangeRequest, BuildState, FileSpec\nfrom .generator import build_spec, apply_instruction, generate_file\nfrom .validator import validate_file, validate_project_against_spec\nfrom .exporter import export_project\n\napp = FastAPI(title='Codem8s Full Stack')\napp.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])\nPROJECTS: dict[str, BuildState] = {}\n\ndef get_project(project_id: str) -> BuildState:\n    state = PROJECTS.get(project_id)\n    if not state:\n        raise HTTPException(404, 'Project not found')\n    return state\n\n@app.post('/projects')\ndef create_project(req: BuildRequest) -> BuildState:\n    spec = build_spec(req.idea, req.stack)\n    files = {path: FileSpec(path=path, purpose=purpose) for path, purpose in spec.files.items()}\n    state = BuildState(project_id=str(uuid4()), spec=spec, files=files, logs=['Spec locked'])\n    PROJECTS[state.project_id] = state\n    return state\n\n@app.post('/projects/{project_id}/change')\ndef change_project(project_id: str, req: ChangeRequest) -> BuildState:\n    state = get_project(project_id)\n    state.spec = apply_instruction(state.spec, req.instruction)\n    for path, purpose in state.spec.files.items():\n        if path not in state.files:\n            state.files[path] = FileSpec(path=path, purpose=purpose)\n    state.logs.append(f'Instruction applied: {req.instruction}')\n    return state\n\n@app.post('/projects/{project_id}/build-next')\ndef build_next(project_id: str) -> BuildState:\n    state = get_project(project_id)\n    pending = [f for f in state.files.values() if f.status != 'valid']\n    if not pending:\n        state.status = 'complete'\n        state.logs.append('All files already valid')\n        return state\n    item = pending[0]\n    content = generate_file(item.path, state.spec)\n    ok, errors = validate_file(item.path, content, state.spec.files)\n    item.content = content if ok else ''\n    item.errors = errors\n    item.status = 'valid' if ok else 'rejected'\n    state.current_file = item.path\n    state.logs.append(('Accepted ' if ok else 'Rejected ') + item.path)\n    return state\n\n@app.post('/projects/{project_id}/validate')\ndef validate_project(project_id: str) -> BuildState:\n    state = get_project(project_id)\n    contents = {p: f.content for p, f in state.files.items() if f.content}\n    ok, errors = validate_project_against_spec(contents, state.spec.files)\n    state.status = 'valid' if ok else 'invalid'\n    state.logs.extend(errors or ['Project valid'])\n    return state\n\n@app.get('/projects/{project_id}/export')\ndef export(project_id: str):\n    state = get_project(project_id)\n    path = export_project(state)\n    return FileResponse(path, filename=f'{state.spec.app_name.replace(' ', '_')}.zip')\n"""
    if path == "backend/runner.py":
        return """from __future__ import annotations\nimport py_compile\nfrom pathlib import Path\nfrom typing import List\n\ndef check_python_file(path: str) -> List[str]:\n    try:\n        py_compile.compile(path, doraise=True)\n        return []\n    except Exception as exc:\n        return [str(exc)]\n\ndef smoke_check_tree(root: str) -> List[str]:\n    errors: List[str] = []\n    for file in Path(root).rglob('*.py'):\n        errors.extend([f'{file}: {err}' for err in check_python_file(str(file))])\n    return errors\n"""
    if path == "backend/exporter.py":
        return """from __future__ import annotations\nfrom pathlib import Path\nfrom zipfile import ZipFile, ZIP_DEFLATED\nfrom .models import BuildState\n\nEXPORT_DIR = Path('exports')\n\ndef export_project(state: BuildState) -> str:\n    EXPORT_DIR.mkdir(exist_ok=True)\n    zip_path = EXPORT_DIR / f'{state.project_id}.zip'\n    with ZipFile(zip_path, 'w', ZIP_DEFLATED) as zf:\n        for path, item in state.files.items():\n            if item.status == 'valid' and item.content:\n                zf.writestr(path, item.content)\n        zf.writestr('codem8s_spec.json', state.spec.model_dump_json(indent=2))\n    return str(zip_path)\n"""
    if path == "backend/generator.py":
        return Path(__file__).read_text(encoding='utf-8')
    if path == "backend/validator.py":
        return Path(__file__).with_name('validator.py').read_text(encoding='utf-8')
    if path == "backend/settings.py":
        return Path(__file__).with_name('settings.py').read_text(encoding='utf-8')
    return f"# Generated file for {path}\nVALUE = {repr(spec.files.get(path, 'project file'))}\n"
