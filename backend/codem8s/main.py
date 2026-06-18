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
from .agent_project_repair import repair_project
from .agent_build_repair import real_build_repair_project

app = FastAPI(title="Codem8s Full Stack")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
PROJECTS: dict[str, BuildState] = {}

MAX_BUILD_ALL_STEPS = 50


def get_project(project_id: str) -> BuildState:
    state = PROJECTS.get(project_id)
    if not state:
        raise HTTPException(404, "Project not found")
    return state


def build_one_file(state: BuildState) -> bool:
    if state.status == "paused":
        state.logs.append("Build paused")
        return False

    pending = [f for f in state.files.values() if f.status != "valid"]
    if not pending:
        state.status = "complete"
        state.logs.append("All files valid")
        return False

    item = pending[0]
    content = generate_file(item.path, state.spec, use_ai=state.use_ai, previous_errors=item.errors)
    ok, errors = validate_file(item.path, content, state.spec.files)

    item.content = content if ok else ""
    item.errors = errors
    item.status = "valid" if ok else "rejected"
    state.current_file = item.path
    state.logs.append(("Accepted " if ok else "Rejected ") + item.path)
    return ok


def apply_repaired_contents(state: BuildState, repaired: dict[str, str]) -> int:
    changed = 0
    for path, content in repaired.items():
        if path not in state.files:
            state.files[path] = FileSpec(path=path, purpose=state.spec.files.get(path, "repaired project file"))

        item = state.files[path]
        if item.content != content:
            ok, errors = validate_file(path, content, state.spec.files)
            if ok:
                item.content = content
                item.status = "valid"
                item.errors = []
                changed += 1
            else:
                item.status = "rejected"
                item.errors = errors
    return changed


def current_contents(state: BuildState) -> dict[str, str]:
    return {path: item.content for path, item in state.files.items() if item.content}


def repair_whole_project(state: BuildState) -> None:
    contents = current_contents(state)
    if not contents:
        return

    try:
        repaired = repair_project(state.spec, contents)
        changed = apply_repaired_contents(state, repaired)
        state.logs.append(f"Whole-project quality repair updated {changed} file(s)" if changed else "Whole-project quality repair checked")
    except Exception as exc:
        state.logs.append(f"Whole-project quality repair skipped: {exc}")


def real_build_check_and_repair(state: BuildState) -> None:
    contents = current_contents(state)
    if not contents:
        return

    try:
        repaired, logs = real_build_repair_project(state.spec, contents, max_rounds=3)
        changed = apply_repaired_contents(state, repaired)
        state.logs.extend(logs)
        state.logs.append(f"Real build repair updated {changed} file(s)" if changed else "Real build repair checked")
    except Exception as exc:
        state.logs.append(f"Real build repair skipped: {exc}")


@app.post("/projects")
def create_project(req: BuildRequest) -> BuildState:
    spec = build_spec(req.idea, req.stack)
    files = {path: FileSpec(path=path, purpose=purpose) for path, purpose in spec.files.items()}
    state = BuildState(
        project_id=str(uuid4()),
        use_ai=req.use_ai,
        spec=spec,
        files=files,
        logs=["Spec locked", f"AI generation: {'on' if req.use_ai else 'off'}"],
    )
    PROJECTS[state.project_id] = state
    return state


@app.post("/projects/{project_id}/change")
def change_project(project_id: str, req: ChangeRequest) -> BuildState:
    state = get_project(project_id)
    state.spec = apply_instruction(state.spec, req.instruction)
    for path, purpose in state.spec.files.items():
        if path not in state.files:
            state.files[path] = FileSpec(path=path, purpose=purpose)
    state.status = "planned"
    state.logs.append(f"Instruction applied: {req.instruction}")
    return state


@app.post("/projects/{project_id}/build-next")
def build_next(project_id: str) -> BuildState:
    state = get_project(project_id)
    build_one_file(state)
    return state


@app.post("/projects/{project_id}/build-all")
def build_all(project_id: str) -> BuildState:
    state = get_project(project_id)
    if state.status == "paused":
        state.logs.append("Resume before building all")
        return state

    state.status = "building"
    for _ in range(MAX_BUILD_ALL_STEPS):
        progressed = build_one_file(state)
        if state.status in {"paused", "complete"}:
            break
        if not progressed:
            break

    if state.status == "complete":
        repair_whole_project(state)
        real_build_check_and_repair(state)

    return state


@app.post("/projects/{project_id}/pause")
def pause_project(project_id: str) -> BuildState:
    state = get_project(project_id)
    state.status = "paused"
    state.logs.append("Paused")
    return state


@app.post("/projects/{project_id}/resume")
def resume_project(project_id: str) -> BuildState:
    state = get_project(project_id)
    if state.status == "paused":
        state.status = "planned"
    state.logs.append("Resumed")
    return state


@app.post("/projects/{project_id}/validate")
def validate_project(project_id: str) -> BuildState:
    state = get_project(project_id)
    repair_whole_project(state)
    real_build_check_and_repair(state)
    contents = current_contents(state)
    ok, errors = validate_project_against_spec(contents, state.spec.files)
    state.status = "valid" if ok else "invalid"
    state.logs.extend(errors or ["Project valid"])
    return state


@app.get("/projects/{project_id}/export")
def export(project_id: str):
    state = get_project(project_id)

    # Export is deterministic. Build/Validate must do repair first.
    if state.status not in {"valid", "complete"}:
        contents = current_contents(state)
        ok, errors = validate_project_against_spec(contents, state.spec.files)
        if not ok:
            raise HTTPException(400, "; ".join(errors) if errors else "Project is not valid")

    path = export_project(state)
    safe_name = state.spec.app_name.replace(" ", "_")
    return FileResponse(path, filename=f"{safe_name}.zip")


@app.get("/settings", response_model=SettingsOut)
def get_settings() -> SettingsOut:
    return settings_status()


@app.post("/settings", response_model=SettingsOut)
def set_settings(settings: SettingsIn) -> SettingsOut:
    return save_settings(settings)
