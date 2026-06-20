from __future__ import annotations
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from uuid import uuid4
from .models import BuildRequest, ChangeRequest, BuildState, FileSpec
from .generator import build_spec, apply_instruction, generate_file
from .validator import validate_file, validate_project_against_spec
from .exporter import export_project
from .settings import SettingsIn, SettingsOut, save_settings, settings_status
from .agent_project_repair import repair_project
from .agent_build_repair import real_build_repair_project
from .sandbox import start_sandbox, stop_sandbox, sandbox_status, sandbox_logs
from .project_store import load_all_projects, load_project, save_project
from .snapshot_store import create_snapshot, list_snapshots, restore_snapshot

app = FastAPI(title="Codem8s Full Stack")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"] , allow_headers=["*"])
PROJECTS: dict[str, BuildState] = load_all_projects()
MAX_BUILD_ALL_STEPS = 50


class SandboxFixRequest(BaseModel):
    instruction: str = "Fix the current sandbox/build error using the blueprint and dependency topology."


class SnapshotRequest(BaseModel):
    label: str = "manual"


def remember(state: BuildState) -> BuildState:
    PROJECTS[state.project_id] = state
    save_project(state)
    return state


def snap(state: BuildState, label: str) -> None:
    try:
        create_snapshot(state, label)
    except Exception as exc:
        state.logs.append(f"Snapshot skipped: {exc}")


def get_project(project_id: str) -> BuildState:
    state = PROJECTS.get(project_id) or load_project(project_id)
    if not state:
        raise HTTPException(404, "Project not found. The project may have been created before persistence was enabled; create/build it once more.")
    PROJECTS[state.project_id] = state
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


def real_build_failed(logs: list[str]) -> bool:
    text = "\n".join(logs).lower()
    return "remaining build problems" in text or "could not repair" in text or "repair failed" in text


def real_build_check_and_repair(state: BuildState) -> bool:
    contents = current_contents(state)
    if not contents:
        return False
    try:
        result = real_build_repair_project(state.spec, contents, max_rounds=6)
        if len(result) == 3:
            repaired, logs, ok = result
        else:
            repaired, logs = result
            ok = not real_build_failed(logs)
        changed = apply_repaired_contents(state, repaired)
        state.logs.extend(logs)
        state.logs.append(f"Real build repair updated {changed} file(s)" if changed else "Real build repair checked")
        if not ok:
            state.status = "invalid"
            state.logs.append("Project invalid: real npm/Python build did not pass")
        return ok
    except Exception as exc:
        state.status = "invalid"
        state.logs.append(f"Real build repair failed: {exc}")
        return False


def project_graph(state: BuildState) -> dict:
    topology = {}
    for entry in reversed(state.spec.change_log):
        if entry.startswith("BLUEPRINT_JSON:"):
            try:
                topology = json.loads(entry.removeprefix("BLUEPRINT_JSON:")).get("dependency_topology", {})
            except Exception:
                topology = {}
            break
    nodes = []
    edges = []
    for path, item in state.files.items():
        meta = topology.get(path, {}) if isinstance(topology, dict) else {}
        nodes.append({"path": path, "status": item.status, "role": meta.get("role") or state.spec.files.get(path, "")})
        for source in meta.get("imports", []) if isinstance(meta, dict) else []:
            edges.append({"from": source, "to": path})
    return {"project_id": state.project_id, "nodes": nodes, "edges": edges}


@app.post("/projects")
def create_project(req: BuildRequest) -> BuildState:
    spec = build_spec(req.idea, req.stack)
    files = {path: FileSpec(path=path, purpose=purpose) for path, purpose in spec.files.items()}
    state = BuildState(project_id=str(uuid4()), use_ai=req.use_ai, spec=spec, files=files, logs=["Spec locked", f"AI generation: {'on' if req.use_ai else 'off'}"])
    remember(state)
    snap(state, "001 created spec")
    return remember(state)


@app.post("/projects/{project_id}/change")
def change_project(project_id: str, req: ChangeRequest) -> BuildState:
    state = get_project(project_id)
    state.spec = apply_instruction(state.spec, req.instruction)
    for path, purpose in state.spec.files.items():
        if path not in state.files:
            state.files[path] = FileSpec(path=path, purpose=purpose)
    state.status = "planned"
    state.logs.append(f"Instruction applied: {req.instruction}")
    snap(state, "instruction applied")
    return remember(state)


@app.post("/projects/{project_id}/build-next")
def build_next(project_id: str) -> BuildState:
    state = get_project(project_id)
    build_one_file(state)
    return remember(state)


@app.post("/projects/{project_id}/build-all")
def build_all(project_id: str) -> BuildState:
    state = get_project(project_id)
    if state.status == "paused":
        state.logs.append("Resume before building all")
        return remember(state)
    snap(state, "before build all")
    state.status = "building"
    for _ in range(MAX_BUILD_ALL_STEPS):
        progressed = build_one_file(state)
        if state.status in {"paused", "complete"}:
            break
        if not progressed:
            break
    if state.status == "complete":
        snap(state, "files generated")
        repair_whole_project(state)
        if real_build_check_and_repair(state):
            state.status = "valid"
    snap(state, "after build all")
    return remember(state)


@app.post("/projects/{project_id}/pause")
def pause_project(project_id: str) -> BuildState:
    state = get_project(project_id)
    state.status = "paused"
    state.logs.append("Paused")
    return remember(state)


@app.post("/projects/{project_id}/resume")
def resume_project(project_id: str) -> BuildState:
    state = get_project(project_id)
    if state.status == "paused":
        state.status = "planned"
    state.logs.append("Resumed")
    return remember(state)


@app.post("/projects/{project_id}/validate")
def validate_project(project_id: str) -> BuildState:
    state = get_project(project_id)
    snap(state, "before validate")
    repair_whole_project(state)
    build_ok = real_build_check_and_repair(state)
    contents = current_contents(state)
    ok, errors = validate_project_against_spec(contents, state.spec.files)
    state.status = "valid" if ok and build_ok else "invalid"
    state.logs.extend(errors or (["Project valid"] if build_ok else ["Project invalid: real build failed"]))
    snap(state, "after validate")
    return remember(state)


@app.get("/projects/{project_id}/graph")
def get_graph(project_id: str):
    return project_graph(get_project(project_id))


@app.post("/projects/{project_id}/snapshot")
def manual_snapshot(project_id: str, req: SnapshotRequest):
    state = get_project(project_id)
    item = create_snapshot(state, req.label)
    state.logs.append(f"Snapshot saved: {item['snapshot_id']} {req.label}")
    remember(state)
    return item


@app.get("/projects/{project_id}/snapshots")
def get_snapshots(project_id: str):
    get_project(project_id)
    return {"project_id": project_id, "snapshots": list_snapshots(project_id)}


@app.post("/projects/{project_id}/restore/{snapshot_id}")
def restore_project_snapshot(project_id: str, snapshot_id: str) -> BuildState:
    restored = restore_snapshot(project_id, snapshot_id)
    if not restored:
        raise HTTPException(404, "Snapshot not found")
    PROJECTS[project_id] = restored
    save_project(restored)
    snap(restored, f"restored {snapshot_id}")
    return remember(restored)


@app.post("/projects/{project_id}/sandbox/start")
def sandbox_start(project_id: str):
    state = get_project(project_id)
    snap(state, "before sandbox start")
    save_project(state)
    return start_sandbox(state)


@app.post("/projects/{project_id}/sandbox/stop")
def sandbox_stop(project_id: str):
    return stop_sandbox(project_id)


@app.get("/projects/{project_id}/sandbox/status")
def sandbox_get_status(project_id: str):
    return sandbox_status(project_id)


@app.get("/projects/{project_id}/sandbox/logs")
def sandbox_get_logs(project_id: str, limit: int = 200):
    return sandbox_logs(project_id, limit=limit)


@app.post("/projects/{project_id}/sandbox/fix")
def sandbox_fix(project_id: str, req: SandboxFixRequest):
    state = get_project(project_id)
    snap(state, "before sandbox fix")
    info = sandbox_status(project_id)
    recent = sandbox_logs(project_id, limit=120).get("logs", [])
    state.logs.append("Sandbox AI fix requested")
    state.logs.append("User instruction: " + req.instruction)
    if info.get("last_error"):
        state.logs.append("Sandbox last error: " + str(info.get("last_error"))[-2000:])
    if recent:
        state.logs.append("Sandbox recent logs:\n" + "\n".join(recent[-40:]))
    repair_whole_project(state)
    if real_build_check_and_repair(state):
        state.status = "valid"
    snap(state, "after sandbox fix")
    remember(state)
    return start_sandbox(state)


@app.get("/projects/{project_id}/export")
def export(project_id: str):
    state = get_project(project_id)
    if state.status != "valid":
        state.logs.append("Snapshot exported while build was not valid")
    snap(state, "exported snapshot")
    path = export_project(state)
    safe_name = state.spec.app_name.replace(" ", "_")
    save_project(state)
    return FileResponse(path, filename=f"{safe_name}_snapshot.zip")


@app.get("/projects/{project_id}/export-snapshot")
def export_snapshot(project_id: str):
    return export(project_id)


@app.get("/settings", response_model=SettingsOut)
def get_settings() -> SettingsOut:
    return settings_status()


@app.post("/settings", response_model=SettingsOut)
def set_settings(settings: SettingsIn) -> SettingsOut:
    return save_settings(settings)
