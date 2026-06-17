from __future__ import annotations
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from uuid import uuid4
from .models import BuildRequest, ChangeRequest, BuildState, FileSpec
from .generator import build_spec, apply_instruction, generate_file
from .validator import validate_file, validate_project_against_spec
from .exporter import export_project
from .settings import SettingsIn, SettingsOut, save_settings, settings_status

app = FastAPI(title="Codem8s Full Stack")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
PROJECTS: dict[str, BuildState] = {}

def get_project(project_id: str) -> BuildState:
    state = PROJECTS.get(project_id)
    if not state:
        raise HTTPException(404, "Project not found")
    return state

@app.post("/projects")
def create_project(req: BuildRequest) -> BuildState:
    spec = build_spec(req.idea, req.stack)
    files = {path: FileSpec(path=path, purpose=purpose) for path, purpose in spec.files.items()}
    state = BuildState(project_id=str(uuid4()), use_ai=req.use_ai, spec=spec, files=files, logs=["Spec locked", f"AI generation: {'on' if req.use_ai else 'off'}"])
    PROJECTS[state.project_id] = state
    return state

@app.post("/projects/{project_id}/change")
def change_project(project_id: str, req: ChangeRequest) -> BuildState:
    state = get_project(project_id)
    state.spec = apply_instruction(state.spec, req.instruction)
    for path, purpose in state.spec.files.items():
        if path not in state.files:
            state.files[path] = FileSpec(path=path, purpose=purpose)
    state.logs.append(f"Instruction applied: {req.instruction}")
    return state

@app.post("/projects/{project_id}/build-next")
def build_next(project_id: str) -> BuildState:
    state = get_project(project_id)
    pending = [f for f in state.files.values() if f.status != "valid"]
    if not pending:
        state.status = "complete"
        state.logs.append("All files already valid")
        return state
    item = pending[0]
    content = generate_file(item.path, state.spec, use_ai=state.use_ai)
    ok, errors = validate_file(item.path, content, state.spec.files)
    item.content = content if ok else ""
    item.errors = errors
    item.status = "valid" if ok else "rejected"
    state.current_file = item.path
    state.logs.append(("Accepted " if ok else "Rejected ") + item.path)
    return state

@app.post("/projects/{project_id}/validate")
def validate_project(project_id: str) -> BuildState:
    state = get_project(project_id)
    contents = {p: f.content for p, f in state.files.items() if f.content}
    ok, errors = validate_project_against_spec(contents, state.spec.files)
    state.status = "valid" if ok else "invalid"
    state.logs.extend(errors or ["Project valid"])
    return state

@app.get("/projects/{project_id}/export")
def export(project_id: str):
    state = get_project(project_id)
    path = export_project(state)
    safe_name = state.spec.app_name.replace(" ", "_")
    return FileResponse(path, filename=f"{safe_name}.zip")


@app.get("/settings", response_model=SettingsOut)
def get_settings() -> SettingsOut:
    return settings_status()

@app.post("/settings", response_model=SettingsOut)
def set_settings(settings: SettingsIn) -> SettingsOut:
    return save_settings(settings)
