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


def _skill_from_agent(agent) -> str:
    skills = getattr(agent, 'skills', []) or []
    priority = ['game', 'crm', 'saas', 'data', 'quality', 'dependency', 'builder', 'validator', 'repair', 'testing', 'ui', 'product']
    for item in priority:
        for skill in skills:
            if item in skill:
                return skill
    return skills[0] if skills else getattr(agent, 'name', 'agent').lower().replace(' ', '-')


def step_from_agent(agent) -> TeamStep:
    name = getattr(agent, 'name', 'Agent')
    role = getattr(agent, 'role', 'Specialist agent')
    skills = getattr(agent, 'skills', []) or []
    skill = _skill_from_agent(agent)
    low = ' '.join([name, role, *skills]).lower()
    if 'game' in low:
        goal = 'Ensure game architecture is playable: loop, state, entities, systems, canvas, HUD, balancing, and import paths.'
    elif 'crm' in low:
        goal = 'Ensure CRM product depth: accounts, contacts, leads, pipeline, activities, notes, reports, and realistic workflows.'
    elif 'saas' in low:
        goal = 'Ensure SaaS depth: dashboard, CRUD flows, permissions, teams, settings, admin states, and realistic data.'
    elif 'data' in low:
        goal = 'Ensure data contracts are coherent across app plan, sample data, UI, API client, and derived metrics.'
    elif 'dependency' in low:
        goal = 'Validate and repair every import path, exported symbol, missing file, and connected dependency chain.'
    elif 'quality' in low:
        goal = 'Score and improve product architecture, UI depth, workflow depth, data richness, and design system quality.'
    elif 'design' in low or 'ui' in low:
        goal = 'Improve responsive UI, visual hierarchy, dashboard sections, empty/loading/error states, and interaction polish.'
    elif 'repair' in low:
        goal = 'Repair connected files from build, sandbox, validation, and quality errors until the project is coherent.'
    elif 'test' in low or 'validator' in low:
        goal = 'Run validation/build reasoning and report exact failing chains with next repair actions.'
    elif 'builder' in low or 'code' in low:
        goal = 'Generate or complete files using the blueprint, topology, previous handoff, and memory.'
    else:
        goal = 'Review project coherence and leave useful handoff notes for the next agent.'
    return TeamStep(name=name, role=role, skill=skill, goal_template=goal)


def default_team_steps() -> list[TeamStep]:
    # Fallback only. Normal project runs should use create_team_run(..., agents=selected_agents).
    fallback = [
        ('Product Architect Agent', 'Plans product model, data contracts, screens, topology, and acceptance criteria.', 'product'),
        ('Dependency Graph Agent', 'Validates imports, exports, missing files, and dependency graph breakages.', 'dependency'),
        ('Builder Agent', 'Generates or completes missing files from the plan and previous handoff.', 'builder'),
        ('Validator Agent', 'Checks import/export contracts, data consistency, product depth, and build readiness.', 'validator'),
        ('Repair Agent', 'Fixes connected dependency chains from validator and build output.', 'repair'),
        ('Tester Agent', 'Runs sandbox/build validation and summarizes final failures or success.', 'testing'),
        ('Quality Agent', 'Scores product architecture and product depth.', 'quality'),
    ]
    return [TeamStep(name=n, role=r, skill=s, goal_template=f'{n}: {r}') for n, r, s in fallback]


def create_team_run(project_id: str, goal: str, agents: list[Any] | None = None) -> TeamRun:
    steps = [step_from_agent(agent) for agent in agents] if agents else default_team_steps()
    run = TeamRun(project_id=project_id, goal=goal, steps=steps)
    return save_team_run(run)


def finish_step(step: TeamStep, status: str, summary: str, actions: list[str], handoff: str, confidence: float) -> TeamStep:
    step.status = status
    step.summary = summary
    step.actions = actions
    step.handoff = handoff
    step.confidence = confidence
    step.finished_at = time.time()
    return step
