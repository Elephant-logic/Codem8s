from __future__ import annotations
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
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
from .agent_registry import AgentCreateRequest, AgentRunRequest, create_agent, find_agent, get_or_create_specialist, list_agents, remember_agent_result
from .agent_memory import MemoryCreateRequest, create_memory, list_memory, search_memory

app = FastAPI(title="Codem8s Full Stack")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
PROJECTS: dict[str, BuildState] = load_all_projects()
MAX_BUILD_ALL_STEPS = 50

class SandboxFixRequest(BaseModel):
    instruction: str = "Fix the current sandbox/build error using the blueprint and dependency topology."

class SnapshotRequest(BaseModel):
    label: str = "manual"

class AutonomousRequest(BaseModel):
    instruction: str = "Work through the project until it runs. Use snapshots, sandbox logs, dependency topology, and repair connected files."
    max_rounds: int = 10


def dump_model(model):
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return json.loads(model.json())


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
        raise HTTPException(404, "Project not found. Create/build it once more.")
    PROJECTS[state.project_id] = state
    return state


def learn_from_errors(state: BuildState, errors: list[str], category: str = "build_failure") -> None:
    for error in errors[:8]:
        text = str(error)[-2000:]
        tags = ["auto-learned"]
        low = text.lower()
        if "export" in low or "import" in low:
            tags += ["imports", "exports", "react"]
        if "vite" in low:
            tags.append("vite")
        if "css" in low or "missing local file" in low:
            tags += ["css", "missing-file"]
        if "dashboard" in low or "shallow" in low:
            tags += ["dashboard", "quality"]
        try:
            create_memory(MemoryCreateRequest(
                project_id=state.project_id,
                category=category,
                pattern=text.split("\n", 1)[0][:180],
                symptom=text,
                fix="Search agent memory, repair the connected dependency chain, then rerun validation/build.",
                lesson=f"Observed in {state.spec.app_name}: {text}",
                tags=sorted(set(tags)),
                success=False,
            ))
        except Exception as exc:
            state.logs.append(f"Agent memory skipped: {exc}")


def memory_context(query: str) -> str:
    matches = search_memory(query, limit=5)
    if not matches:
        return "No matching memory yet."
    return "\n".join(f"- {m.pattern}: {m.fix or m.lesson}" for m in matches)


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
    hints = memory_context(" ".join(item.errors or []) + " " + item.path)
    previous = list(item.errors or [])
    if hints and hints != "No matching memory yet.":
        previous.append("Relevant agent memory:\n" + hints)
    content = generate_file(item.path, state.spec, use_ai=state.use_ai, previous_errors=previous)
    ok, errors = validate_file(item.path, content, state.spec.files)
    item.content = content if ok else ""
    item.errors = errors
    item.status = "valid" if ok else "rejected"
    state.current_file = item.path
    state.logs.append(("Accepted " if ok else "Rejected ") + item.path)
    if errors:
        learn_from_errors(state, [f"{item.path}: {err}" for err in errors], category="file_validation")
    return True


def apply_repaired_contents(state: BuildState, repaired: dict[str, str]) -> int:
    changed = 0
    for path, content in repaired.items():
        if path not in state.files:
            state.files[path] = FileSpec(path=path, purpose=state.spec.files.get(path, "repaired project file"))
        item = state.files[path]
        if item.content != content:
            ok, errors = validate_file(path, content, state.spec.files)
            if ok:
                item.content, item.status, item.errors = content, "valid", []
                changed += 1
            else:
                item.status, item.errors = "rejected", errors
                learn_from_errors(state, [f"{path}: {err}" for err in errors], category="repair_rejected")
    return changed


def current_contents(state: BuildState) -> dict[str, str]:
    return {path: item.content for path, item in state.files.items() if item.content}


def repair_whole_project(state: BuildState) -> None:
    contents = current_contents(state)
    if not contents:
        return
    try:
        state.logs.append("Agent memory used:\n" + memory_context(" ".join(state.logs[-20:])))
        repaired = repair_project(state.spec, contents)
        changed = apply_repaired_contents(state, repaired)
        state.logs.append(f"Whole-project quality repair updated {changed} file(s)" if changed else "Whole-project quality repair checked")
    except Exception as exc:
        state.logs.append(f"Whole-project quality repair skipped: {exc}")


def real_build_failed(logs: list[str]) -> bool:
    text = "\n".join(logs).lower()
    return "remaining build problems" in text or "could not repair" in text or "repair failed" in text


def real_build_check_and_repair(state: BuildState, rounds: int = 6) -> bool:
    contents = current_contents(state)
    if not contents:
        return False
    try:
        result = real_build_repair_project(state.spec, contents, max_rounds=rounds)
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
            learn_from_errors(state, logs, category="real_build_failure")
        else:
            create_memory(MemoryCreateRequest(project_id=state.project_id, category="successful_repair", pattern="real build passed", fix="Current repair flow produced a passing build", lesson="Build repair succeeded for this project", tags=["build", "success"], success=True))
        return bool(ok)
    except Exception as exc:
        state.status = "invalid"
        state.logs.append(f"Real build repair failed: {exc}")
        learn_from_errors(state, [str(exc)], category="repair_exception")
        return False


def mark_validity(state: BuildState, build_ok: bool) -> bool:
    ok, errors = validate_project_against_spec(current_contents(state), state.spec.files)
    state.status = "valid" if ok and build_ok else "invalid"
    if errors:
        state.logs.extend(errors[:30])
        learn_from_errors(state, errors, category="project_validation")
    else:
        state.logs.extend(["Project valid"] if build_ok else ["Project invalid: real build failed"])
    return state.status == "valid"


def run_agent_on_state(state: BuildState, req: AgentRunRequest) -> dict:
    agent = find_agent(skill=req.skill, agent_id=req.agent_id) or get_or_create_specialist(req.goal)
    goal = req.goal or "Work on the current project using your specialist role."
    state.logs.append(f"Agent started: {agent.name}")
    state.logs.append(f"Agent role: {agent.role}")
    state.logs.append(f"Agent goal: {goal}")
    state.logs.append("Agent memory context:\n" + memory_context(goal + " " + " ".join(state.logs[-20:])))
    snap(state, f"agent {agent.name} start")
    role_text = " ".join([agent.name, agent.role, *agent.skills, goal]).lower()
    success = None
    if any(term in role_text for term in ["repair", "validator", "tester", "build", "dependency", "vite", "import", "export"]):
        repair_whole_project(state)
        build_ok = real_build_check_and_repair(state, rounds=4)
        success = mark_validity(state, build_ok)
    elif any(term in role_text for term in ["architect", "plan", "topology"]):
        state.logs.append("Architect Agent reviewed blueprint, topology, files, and acceptance criteria")
    elif any(term in role_text for term in ["design", "ui", "ux", "dashboard", "css"]):
        state.logs.append("Designer Agent marked UI/design pass for next generation or repair round")
        repair_whole_project(state)
    else:
        state.logs.append("Specialist Agent recorded project context for future tasks")
    memory = " | ".join(state.logs[-12:])
    agent = remember_agent_result(agent, state.project_id, memory=memory, success=success)
    create_memory(MemoryCreateRequest(agent_id=agent.agent_id, project_id=state.project_id, category="agent_handoff", pattern=f"{agent.name} ran", lesson=memory, tags=["agent", *agent.skills], success=success))
    snap(state, f"agent {agent.name} finish")
    remember(state)
    return {"agent": dump_model(agent), "project": state, "timeline": timeline_for(state)}


def project_graph(state: BuildState) -> dict:
    topology = {}
    for entry in reversed(state.spec.change_log):
        if entry.startswith("BLUEPRINT_JSON:"):
            try:
                topology = json.loads(entry.removeprefix("BLUEPRINT_JSON:")).get("dependency_topology", {})
            except Exception:
                topology = {}
            break
    nodes, edges = [], []
    for path, item in state.files.items():
        meta = topology.get(path, {}) if isinstance(topology, dict) else {}
        nodes.append({"path": path, "status": item.status, "role": meta.get("role") or state.spec.files.get(path, "")})
        for source in meta.get("imports", []) if isinstance(meta, dict) else []:
            edges.append({"from": source, "to": path})
    return {"project_id": state.project_id, "nodes": nodes, "edges": edges}


def timeline_for(state: BuildState) -> dict:
    events = []
    for item in list_snapshots(state.project_id):
        events.append({"kind": "snapshot", "title": "Snapshot saved", "detail": f"{item.get('snapshot_id')} — {item.get('label')}", "status": item.get("status"), "created_at": item.get("created_at")})
    for index, line in enumerate(state.logs[-180:]):
        lower = line.lower(); kind = "log"; title = "Log"
        if "spec locked" in lower: kind, title = "plan", "Blueprint/spec locked"
        elif line.startswith("Accepted "): kind, title = "file", "File accepted"
        elif line.startswith("Rejected "): kind, title = "error", "File rejected"
        elif "agent memory" in lower: kind, title = "memory", "Agent memory"
        elif "agent" in lower: kind, title = "agent", "Agent activity"
        elif "autonomous" in lower: kind, title = "auto", "Autonomous mode"
        elif "sandbox" in lower and "fix" in lower: kind, title = "repair", "Sandbox repair"
        elif "real build repair" in lower or "dependency-aware" in lower: kind, title = "repair", "Real build repair"
        elif "failed" in lower or "invalid" in lower: kind, title = "error", "Build failed"
        elif "project valid" in lower or "build passed" in lower: kind, title = "success", "Build passed"
        elif "snapshot" in lower: kind, title = "snapshot", "Snapshot"
        elif "instruction" in lower: kind, title = "instruction", "User instruction"
        events.append({"kind": kind, "title": title, "detail": line, "created_at": float(index)})
    events.sort(key=lambda e: e.get("created_at") or 0)
    return {"project_id": state.project_id, "events": events[-240:]}


def fill_missing_files(state: BuildState, limit: int = 80) -> None:
    state.status = "building"
    for _ in range(limit):
        pending = [f for f in state.files.values() if f.status != "valid"]
        if not pending:
            state.status = "complete"
            state.logs.append("All planned files generated")
            return
        build_one_file(state)


def autonomous_run(state: BuildState, req: AutonomousRequest) -> dict:
    max_rounds = max(1, min(req.max_rounds or 10, 20))
    state.logs.append(f"Autonomous mode started for up to {max_rounds} round(s)")
    state.logs.append("Instruction: " + req.instruction)
    snap(state, "autonomous start")
    result = {"build_ok": False, "last_error": "not run"}
    last_error = ""
    repeated = 0
    for round_no in range(1, max_rounds + 1):
        state.logs.append(f"Autonomous round {round_no}: generate missing files")
        fill_missing_files(state, limit=80)
        snap(state, f"autonomous round {round_no} before repair")
        repair_whole_project(state)
        build_ok = real_build_check_and_repair(state, rounds=3)
        mark_validity(state, build_ok)
        remember(state)
        result = start_sandbox(state)
        snap(state, f"autonomous round {round_no} after sandbox")
        remember(state)
        if result.get("build_ok") or state.status == "valid":
            state.status = "valid"
            state.logs.append(f"Autonomous mode finished: build passed on round {round_no}")
            snap(state, "autonomous build passed")
            remember(state)
            return result
        signature = str(result.get("last_error") or "")[-1500:]
        repeated = repeated + 1 if signature and signature == last_error else 0
        last_error = signature
        if repeated >= 1:
            state.logs.append("Autonomous mode paused: same error repeated. Add steering instruction and run again.")
            state.status = "invalid"
            remember(state)
            return result
    state.logs.append("Autonomous mode paused: round limit reached. Add steering instruction and run again.")
    state.status = "invalid"
    remember(state)
    return result


def sse(data: dict) -> str:
    return "data: " + json.dumps(data, default=str) + "\n\n"


def autonomous_stream_events(state: BuildState, instruction: str, max_rounds: int):
    max_rounds = max(1, min(max_rounds or 10, 20))
    state.logs.append(f"Autonomous stream started for up to {max_rounds} round(s)")
    state.logs.append("Instruction: " + instruction)
    state.logs.append("Agent memory context:\n" + memory_context(instruction))
    snap(state, "autonomous stream start")
    remember(state)
    yield sse({"kind": "auto", "title": "Autonomous mode started", "detail": instruction, "status": state.status})
    last_error = ""
    repeated = 0
    for round_no in range(1, max_rounds + 1):
        yield sse({"kind": "auto", "title": f"Round {round_no}", "detail": "Generating missing files", "status": state.status})
        fill_missing_files(state, limit=80)
        snap(state, f"stream round {round_no} generated")
        remember(state)
        yield sse({"kind": "snapshot", "title": "Snapshot saved", "detail": f"Round {round_no} generated files", "status": state.status})
        yield sse({"kind": "repair", "title": f"Round {round_no}", "detail": "Repairing whole project and connected build errors", "status": state.status})
        repair_whole_project(state)
        build_ok = real_build_check_and_repair(state, rounds=3)
        mark_validity(state, build_ok)
        remember(state)
        yield sse({"kind": "repair", "title": "Repair finished", "detail": state.logs[-1] if state.logs else "repair complete", "status": state.status})
        yield sse({"kind": "sandbox", "title": f"Round {round_no}", "detail": "Starting sandbox", "status": state.status})
        result = start_sandbox(state)
        snap(state, f"stream round {round_no} sandbox")
        remember(state)
        if result.get("build_ok") or state.status == "valid":
            state.status = "valid"
            state.logs.append(f"Autonomous stream finished: build passed on round {round_no}")
            snap(state, "autonomous stream build passed")
            remember(state)
            yield sse({"kind": "success", "title": "Build passed", "detail": f"Passed on round {round_no}", "status": state.status, "done": True})
            return
        signature = str(result.get("last_error") or "")[-1500:]
        yield sse({"kind": "error", "title": "Build not green", "detail": signature or "Sandbox did not report green", "status": state.status})
        repeated = repeated + 1 if signature and signature == last_error else 0
        last_error = signature
        if repeated >= 1:
            state.status = "invalid"
            state.logs.append("Autonomous stream paused: same error repeated. Add steering instruction and run again.")
            learn_from_errors(state, [signature], category="autonomous_repeated_error")
            remember(state)
            yield sse({"kind": "pause", "title": "Paused", "detail": "Same error repeated. Add steering instruction and run again.", "status": state.status, "done": True})
            return
    state.status = "invalid"
    state.logs.append("Autonomous stream paused: round limit reached. Add steering instruction and run again.")
    remember(state)
    yield sse({"kind": "pause", "title": "Paused", "detail": "Round limit reached. Add steering instruction and run again.", "status": state.status, "done": True})

@app.get("/agents")
def agents_list():
    return {"agents": [dump_model(agent) for agent in list_agents()]}

@app.post("/agents")
def agents_create(req: AgentCreateRequest):
    return create_agent(req)

@app.post("/agents/factory")
def agents_factory(req: AgentRunRequest):
    agent = get_or_create_specialist(req.goal)
    return agent

@app.get("/agent-memory")
def agent_memory_list(query: str | None = None, category: str | None = None, tag: str | None = None, limit: int = 100):
    records = search_memory(query, limit=limit) if query else list_memory(category=category, tag=tag, limit=limit)
    return {"memory": [dump_model(record) for record in records]}

@app.post("/agent-memory")
def agent_memory_create(req: MemoryCreateRequest):
    return create_memory(req)

@app.post("/projects")
def create_project(req: BuildRequest) -> BuildState:
    spec = build_spec(req.idea, req.stack)
    files = {path: FileSpec(path=path, purpose=purpose) for path, purpose in spec.files.items()}
    state = BuildState(project_id=str(uuid4()), use_ai=req.use_ai, spec=spec, files=files, logs=["Spec locked", f"AI generation: {'on' if req.use_ai else 'off'}"])
    state.logs.append("Agent memory context:\n" + memory_context(req.idea))
    remember(state); snap(state, "001 created spec")
    specialist = get_or_create_specialist(req.idea)
    remember_agent_result(specialist, state.project_id, f"Created project from idea: {req.idea}")
    state.logs.append(f"Agent assigned: {specialist.name}")
    return remember(state)

@app.post("/projects/{project_id}/agents/run")
def project_agent_run(project_id: str, req: AgentRunRequest):
    return run_agent_on_state(get_project(project_id), req)

@app.post("/projects/{project_id}/change")
def change_project(project_id: str, req: ChangeRequest) -> BuildState:
    state = get_project(project_id)
    state.spec = apply_instruction(state.spec, req.instruction)
    for path, purpose in state.spec.files.items():
        if path not in state.files:
            state.files[path] = FileSpec(path=path, purpose=purpose)
    state.status = "planned"; state.logs.append(f"Instruction applied: {req.instruction}")
    state.logs.append("Agent memory context:\n" + memory_context(req.instruction))
    specialist = get_or_create_specialist(req.instruction)
    remember_agent_result(specialist, state.project_id, f"Instruction applied: {req.instruction}")
    state.logs.append(f"Agent assigned: {specialist.name}")
    snap(state, "instruction applied")
    return remember(state)

@app.post("/projects/{project_id}/build-next")
def build_next(project_id: str) -> BuildState:
    state = get_project(project_id); build_one_file(state); return remember(state)

@app.post("/projects/{project_id}/build-all")
def build_all(project_id: str) -> BuildState:
    state = get_project(project_id)
    if state.status == "paused":
        state.logs.append("Resume before building all"); return remember(state)
    snap(state, "before build all")
    fill_missing_files(state, MAX_BUILD_ALL_STEPS)
    if state.status == "complete":
        snap(state, "files generated"); repair_whole_project(state)
        if real_build_check_and_repair(state): state.status = "valid"
    snap(state, "after build all")
    return remember(state)

@app.post("/projects/{project_id}/pause")
def pause_project(project_id: str) -> BuildState:
    state = get_project(project_id); state.status = "paused"; state.logs.append("Paused"); return remember(state)

@app.post("/projects/{project_id}/resume")
def resume_project(project_id: str) -> BuildState:
    state = get_project(project_id)
    if state.status == "paused": state.status = "planned"
    state.logs.append("Resumed"); return remember(state)

@app.post("/projects/{project_id}/validate")
def validate_project(project_id: str) -> BuildState:
    state = get_project(project_id); snap(state, "before validate")
    repair_whole_project(state); build_ok = real_build_check_and_repair(state)
    mark_validity(state, build_ok); snap(state, "after validate")
    return remember(state)

@app.post("/projects/{project_id}/autonomous")
def autonomous_project(project_id: str, req: AutonomousRequest):
    state = get_project(project_id)
    result = autonomous_run(state, req)
    return {"project": remember(state), "sandbox": result, "timeline": timeline_for(state)}

@app.get("/projects/{project_id}/autonomous/stream")
def autonomous_project_stream(project_id: str, instruction: str = "Work through the project until it runs.", max_rounds: int = 10):
    state = get_project(project_id)
    return StreamingResponse(autonomous_stream_events(state, instruction, max_rounds), media_type="text/event-stream")

@app.get("/projects/{project_id}/graph")
def get_graph(project_id: str): return project_graph(get_project(project_id))

@app.get("/projects/{project_id}/timeline")
def get_timeline(project_id: str): return timeline_for(get_project(project_id))

@app.post("/projects/{project_id}/snapshot")
def manual_snapshot(project_id: str, req: SnapshotRequest):
    state = get_project(project_id); item = create_snapshot(state, req.label)
    state.logs.append(f"Snapshot saved: {item['snapshot_id']} {req.label}"); remember(state)
    return item

@app.get("/projects/{project_id}/snapshots")
def get_snapshots(project_id: str):
    get_project(project_id); return {"project_id": project_id, "snapshots": list_snapshots(project_id)}

@app.post("/projects/{project_id}/restore/{snapshot_id}")
def restore_project_snapshot(project_id: str, snapshot_id: str) -> BuildState:
    restored = restore_snapshot(project_id, snapshot_id)
    if not restored: raise HTTPException(404, "Snapshot not found")
    PROJECTS[project_id] = restored; save_project(restored); snap(restored, f"restored {snapshot_id}")
    return remember(restored)

@app.post("/projects/{project_id}/sandbox/start")
def sandbox_start(project_id: str):
    state = get_project(project_id); snap(state, "before sandbox start"); save_project(state); return start_sandbox(state)

@app.post("/projects/{project_id}/sandbox/stop")
def sandbox_stop(project_id: str): return stop_sandbox(project_id)

@app.get("/projects/{project_id}/sandbox/status")
def sandbox_get_status(project_id: str): return sandbox_status(project_id)

@app.get("/projects/{project_id}/sandbox/logs")
def sandbox_get_logs(project_id: str, limit: int = 200): return sandbox_logs(project_id, limit=limit)

@app.post("/projects/{project_id}/sandbox/fix")
def sandbox_fix(project_id: str, req: SandboxFixRequest):
    state = get_project(project_id); snap(state, "before sandbox fix")
    info = sandbox_status(project_id); recent = sandbox_logs(project_id, limit=120).get("logs", [])
    state.logs.append("Sandbox AI fix requested"); state.logs.append("User instruction: " + req.instruction)
    state.logs.append("Agent memory context:\n" + memory_context(req.instruction + " " + str(info.get("last_error") or "")))
    if info.get("last_error"):
        state.logs.append("Sandbox last error: " + str(info.get("last_error"))[-2000:])
        learn_from_errors(state, [str(info.get("last_error"))], category="sandbox_failure")
    if recent: state.logs.append("Sandbox recent logs:\n" + "\n".join(recent[-40:]))
    agent = get_or_create_specialist(req.instruction + " dependency build repair")
    remember_agent_result(agent, state.project_id, f"Sandbox fix requested: {req.instruction}")
    state.logs.append(f"Agent assigned: {agent.name}")
    repair_whole_project(state)
    if real_build_check_and_repair(state): state.status = "valid"
    snap(state, "after sandbox fix"); remember(state)
    return start_sandbox(state)

@app.get("/projects/{project_id}/export")
def export(project_id: str):
    state = get_project(project_id)
    if state.status != "valid": state.logs.append("Snapshot exported while build was not valid")
    snap(state, "exported snapshot"); path = export_project(state)
    safe_name = state.spec.app_name.replace(" ", "_"); save_project(state)
    return FileResponse(path, filename=f"{safe_name}_snapshot.zip")

@app.get("/projects/{project_id}/export-snapshot")
def export_snapshot(project_id: str): return export(project_id)

@app.get("/settings", response_model=SettingsOut)
def get_settings() -> SettingsOut: return settings_status()

@app.post("/settings", response_model=SettingsOut)
def set_settings(settings: SettingsIn) -> SettingsOut: return save_settings(settings)
