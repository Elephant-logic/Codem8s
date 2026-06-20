from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

STORE_DIR = Path('/opt/render/.codem8s/agent_teams')
FALLBACK_DIR = Path('/tmp/codem8s_agent_teams')


class TeamStep(BaseModel):
    name: str
    role: str
    skill: str
    goal_template: str
    status: str = 'waiting'
    summary: str = ''
    actions: list[str] = Field(default_factory=list)
    handoff: str = ''
    confidence: float = 0.0
    started_at: float | None = None
    finished_at: float | None = None


class TeamRun(BaseModel):
    team_run_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    goal: str
    status: str = 'created'
    steps: list[TeamStep] = Field(default_factory=list)
    handoffs: list[dict[str, Any]] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class TeamRunRequest(BaseModel):
    goal: str = 'Build and repair this project as an agent team until it is coherent and buildable.'
    max_cycles: int = 1


def team_dir() -> Path:
    try:
        STORE_DIR.mkdir(parents=True, exist_ok=True)
        test = STORE_DIR / '.write_test'
        test.write_text('ok', encoding='utf-8')
        test.unlink(missing_ok=True)
        return STORE_DIR
    except Exception:
        FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
        return FALLBACK_DIR


def dump_model(model) -> dict[str, Any]:
    if hasattr(model, 'model_dump'):
        return model.model_dump(mode='json')
    return json.loads(model.json())


def save_team_run(run: TeamRun) -> TeamRun:
    run.updated_at = time.time()
    safe = ''.join(ch for ch in run.team_run_id if ch.isalnum() or ch in '-_')
    (team_dir() / f'{safe}.json').write_text(json.dumps(dump_model(run), indent=2), encoding='utf-8')
    return run


def _load(path: Path) -> TeamRun | None:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if hasattr(TeamRun, 'model_validate'):
            return TeamRun.model_validate(data)
        return TeamRun.parse_obj(data)
    except Exception:
        return None


def list_team_runs(project_id: str | None = None, limit: int = 50) -> list[TeamRun]:
    runs: list[TeamRun] = []
    for path in team_dir().glob('*.json'):
        run = _load(path)
        if not run:
            continue
        if project_id and run.project_id != project_id:
            continue
        runs.append(run)
    runs.sort(key=lambda item: item.updated_at, reverse=True)
    return runs[:max(1, min(limit, 200))]


def get_team_run(team_run_id: str) -> TeamRun | None:
    safe = ''.join(ch for ch in team_run_id if ch.isalnum() or ch in '-_')
    path = team_dir() / f'{safe}.json'
    return _load(path) if path.exists() else None


def default_team_steps() -> list[TeamStep]:
    return [
        TeamStep(
            name='Architect Agent',
            role='Plans product model, data contracts, screens, topology, and acceptance criteria.',
            skill='architect',
            goal_template='Review blueprint, app plan, entities, topology, and identify missing coherence before building.',
        ),
        TeamStep(
            name='Builder Agent',
            role='Generates or completes missing files from the plan and previous handoff.',
            skill='builder',
            goal_template='Generate missing files and complete shallow files using the architect handoff and project plan.',
        ),
        TeamStep(
            name='Validator Agent',
            role='Checks import/export contracts, missing files, package dependencies, data-model consistency, and product depth.',
            skill='validator',
            goal_template='Validate project consistency and report exact failing chains for repair.',
        ),
        TeamStep(
            name='Repair Agent',
            role='Fixes connected dependency chains from validator and build output.',
            skill='repair',
            goal_template='Repair the connected graph: imports, exports, missing files, data contracts, and build failures.',
        ),
        TeamStep(
            name='Tester Agent',
            role='Runs sandbox/build validation and summarizes final failures or success.',
            skill='tester',
            goal_template='Run build/sandbox checks, verify status, and produce final handoff.',
        ),
        TeamStep(
            name='Designer Agent',
            role='Improves UI/UX, responsive layout, dashboard depth, and visual system.',
            skill='design',
            goal_template='Review and improve UI depth, design system, empty/loading/error states, and dashboard quality.',
        ),
    ]


def create_team_run(project_id: str, goal: str) -> TeamRun:
    run = TeamRun(project_id=project_id, goal=goal, steps=default_team_steps())
    return save_team_run(run)


def finish_step(step: TeamStep, status: str, summary: str, actions: list[str], handoff: str, confidence: float) -> TeamStep:
    step.status = status
    step.summary = summary
    step.actions = actions
    step.handoff = handoff
    step.confidence = confidence
    step.finished_at = time.time()
    return step
