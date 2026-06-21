from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

STORE_DIR = Path('/opt/render/.codem8s/agents')
FALLBACK_DIR = Path('/tmp/codem8s_agents')


class AgentSpec(BaseModel):
    agent_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    role: str
    skills: list[str] = Field(default_factory=list)
    system_prompt: str
    quality_checklist: list[str] = Field(default_factory=list)
    memory: list[str] = Field(default_factory=list)
    files_owned: list[str] = Field(default_factory=list)
    projects_used: list[str] = Field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class AgentCreateRequest(BaseModel):
    name: str
    role: str
    skills: list[str] = Field(default_factory=list)
    system_prompt: str = ''
    quality_checklist: list[str] = Field(default_factory=list)
    files_owned: list[str] = Field(default_factory=list)


class AgentRunRequest(BaseModel):
    goal: str = 'Work on the current project using your specialist role.'
    agent_id: str | None = None
    skill: str | None = None


def agent_dir() -> Path:
    try:
        STORE_DIR.mkdir(parents=True, exist_ok=True)
        test = STORE_DIR / '.write_test'
        test.write_text('ok', encoding='utf-8')
        test.unlink(missing_ok=True)
        return STORE_DIR
    except Exception:
        FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
        return FALLBACK_DIR


def _dump(agent: AgentSpec) -> dict[str, Any]:
    if hasattr(agent, 'model_dump'):
        return agent.model_dump(mode='json')
    return json.loads(agent.json())


def _load(path: Path) -> AgentSpec | None:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if hasattr(AgentSpec, 'model_validate'):
            return AgentSpec.model_validate(data)
        return AgentSpec.parse_obj(data)
    except Exception:
        return None


def save_agent(agent: AgentSpec) -> AgentSpec:
    agent.updated_at = time.time()
    safe = ''.join(ch for ch in agent.agent_id if ch.isalnum() or ch in '-_')
    (agent_dir() / f'{safe}.json').write_text(json.dumps(_dump(agent), indent=2), encoding='utf-8')
    return agent


def list_agents() -> list[AgentSpec]:
    seed_default_agents()
    agents: list[AgentSpec] = []
    for path in agent_dir().glob('*.json'):
        agent = _load(path)
        if agent:
            agents.append(agent)
    return sorted(agents, key=lambda item: (item.name.lower(), item.created_at))


def get_agent(agent_id: str) -> AgentSpec | None:
    for agent in list_agents():
        if agent.agent_id == agent_id:
            return agent
    return None


def create_agent(req: AgentCreateRequest) -> AgentSpec:
    prompt = req.system_prompt.strip() or default_prompt(req.name, req.role, req.skills)
    agent = AgentSpec(
        name=req.name,
        role=req.role,
        skills=req.skills,
        system_prompt=prompt,
        quality_checklist=req.quality_checklist or default_checklist(req.role, req.skills),
        files_owned=req.files_owned,
    )
    return save_agent(agent)


def default_prompt(name: str, role: str, skills: list[str]) -> str:
    skill_text = ', '.join(skills) or role
    return (
        f'You are {name}, a Codem8s specialist agent. Role: {role}. '
        f'Skills: {skill_text}. Work from the saved blueprint, dependency topology, sandbox logs, validator output, and agent memory. '
        'Do not make isolated changes. Fix connected files as a graph. Prefer coherent product quality over file count. '
        'Write lessons back to memory so future projects avoid repeated mistakes.'
    )


def default_checklist(role: str, skills: list[str]) -> list[str]:
    base = [
        'Respect blueprint and dependency topology',
        'Check import/export contracts',
        'Avoid placeholders and generic shallow output',
        'Keep generated files buildable',
        'Record useful lessons in memory',
    ]
    role_low = ' '.join([role, *skills]).lower()
    if 'design' in role_low or 'ui' in role_low:
        base.extend(['Use responsive layout', 'Use premium design system', 'Check empty/loading/error states'])
    if 'test' in role_low or 'validator' in role_low:
        base.extend(['Run real build mentally or through sandbox', 'Report exact failing chain'])
    if 'repair' in role_low or 'dependency' in role_low:
        base.extend(['Repair all files in the failing dependency chain', 'Do not stop after first error'])
    if 'architect' in role_low or 'product' in role_low:
        base.extend(['Define data model, user flows, navigation, and acceptance criteria first'])
    if 'game' in role_low:
        base.extend(['Keep game loop, state, systems, entities, UI and canvas imports consistent', 'Make the game playable, not just renderable'])
    if 'crm' in role_low or 'saas' in role_low:
        base.extend(['Include realistic workflows, permissions, records, dashboards and activity history'])
    return base


def _default_agent_requests() -> list[AgentCreateRequest]:
    return [
        AgentCreateRequest(name='Architect Agent', role='Plans product, data model, screens, topology, user flows, and acceptance criteria', skills=['planning', 'topology', 'data-model', 'product']),
        AgentCreateRequest(name='Builder Agent', role='Generates files from the product plan and topology', skills=['code-generation', 'react', 'fastapi']),
        AgentCreateRequest(name='Validator Agent', role='Checks imports, exports, missing files, package deps, and product depth', skills=['validation', 'static-analysis', 'quality-gates']),
        AgentCreateRequest(name='Repair Agent', role='Fixes connected files from build and sandbox errors', skills=['repair', 'dependency-graph', 'vite-errors']),
        AgentCreateRequest(name='Designer Agent', role='Improves UI, UX, CSS, layout, visual hierarchy, and responsive design', skills=['ui', 'ux', 'css', 'design-system']),
        AgentCreateRequest(name='Tester Agent', role='Runs sandbox/build reasoning and reports failures with likely causes', skills=['testing', 'sandbox', 'build-logs']),
        AgentCreateRequest(name='Dependency Graph Agent', role='Validates and repairs import paths, named/default exports, missing files, and graph-connected breakages', skills=['dependency', 'imports', 'exports', 'vite', 'graph', 'repair']),
        AgentCreateRequest(name='Quality Agent', role='Scores product architecture, UI depth, workflow depth, data richness, and design system quality', skills=['quality', 'product-quality', 'ui-depth', 'workflow-depth']),
        AgentCreateRequest(name='Product Architect Agent', role='Turns ideas into real product architecture with personas, workflows, permissions, reports, automations, and acceptance criteria', skills=['product', 'architect', 'workflows', 'acceptance-criteria']),
        AgentCreateRequest(name='Game Agent', role='Specialist for game architecture, loops, entities, systems, canvas scenes, balancing, HUD, and playable mechanics', skills=['game', 'canvas', 'game-loop', 'entities', 'systems', 'balancing']),
        AgentCreateRequest(name='SaaS Agent', role='Specialist for SaaS dashboards, CRUD workflows, teams, permissions, billing-style UX, and admin panels', skills=['saas', 'dashboard', 'crud', 'permissions', 'teams']),
        AgentCreateRequest(name='CRM Agent', role='Specialist for CRM accounts, contacts, leads, pipelines, deals, activities, notes, reports, and sales workflows', skills=['crm', 'pipeline', 'sales', 'contacts', 'activity-history']),
        AgentCreateRequest(name='Data Model Agent', role='Specialist for coherent sample data, app plans, entity contracts, relationships, and derived metrics', skills=['data', 'sample-data', 'entities', 'contracts', 'metrics']),
    ]


def seed_default_agents() -> None:
    existing_names = {agent.name for agent in [a for a in (_load(p) for p in agent_dir().glob('*.json')) if a]}
    for req in _default_agent_requests():
        if req.name not in existing_names:
            create_agent(req)


def find_agent(skill: str | None = None, agent_id: str | None = None) -> AgentSpec | None:
    if agent_id:
        return get_agent(agent_id)
    agents = list_agents()
    if not skill:
        return agents[0] if agents else None
    needle = skill.lower()
    for agent in agents:
        haystack = ' '.join([agent.name, agent.role, *agent.skills]).lower()
        if needle in haystack:
            return agent
    return None


def infer_specialist_name(goal: str) -> tuple[str, str, list[str]]:
    low = goal.lower()
    if any(term in low for term in ['tower', 'wave', 'enemy', 'canvas', 'game', 'projectile', 'hud', 'level', 'sprite']):
        return 'Game Agent', 'Specialist for game architecture, loops, entities, systems, canvas scenes, balancing, HUD, and playable mechanics', ['game', 'canvas', 'game-loop', 'entities', 'systems', 'balancing']
    if any(term in low for term in ['crm', 'lead', 'pipeline', 'sales', 'deal', 'account', 'contact']):
        return 'CRM Agent', 'Specialist for CRM accounts, contacts, leads, pipelines, deals, activities, notes, reports, and sales workflows', ['crm', 'pipeline', 'sales', 'contacts', 'activity-history']
    if any(term in low for term in ['saas', 'admin', 'dashboard', 'team', 'permission', 'settings', 'workspace']):
        return 'SaaS Agent', 'Specialist for SaaS dashboards, CRUD workflows, teams, permissions, and admin panels', ['saas', 'dashboard', 'crud', 'permissions', 'teams']
    if any(term in low for term in ['export', 'zip', 'github', 'save', 'snapshot']):
        return 'Persistence Agent', 'Specialist for saving, exporting, restoring, project state, and snapshots', ['persistence', 'snapshots', 'export']
    if any(term in low for term in ['import', 'export', 'missing', 'vite', 'build', 'dependency', 'module not found', 'unresolved_import']):
        return 'Dependency Graph Agent', 'Specialist for import/export graphs, package dependencies, Vite build errors, and connected repair', ['dependency', 'imports', 'exports', 'vite', 'repair']
    if any(term in low for term in ['design', 'layout', 'ui', 'responsive', 'visual', 'css']):
        return 'Designer Agent', 'Specialist for polished UI, dashboards, interaction states, and responsive design systems', ['ui', 'ux', 'dashboard', 'css']
    if any(term in low for term in ['quality', 'shallow', 'workflow', 'product', 'architecture']):
        return 'Quality Agent', 'Specialist for product quality scoring, depth checks, and acceptance criteria', ['quality', 'product-quality', 'ui-depth', 'workflow-depth']
    return 'Project Specialist Agent', 'Specialist created for this project request', ['project-specialist']


def get_or_create_specialist(goal: str) -> AgentSpec:
    name, role, skills = infer_specialist_name(goal)
    for agent in list_agents():
        if agent.name == name:
            return agent
    return create_agent(AgentCreateRequest(name=name, role=role, skills=skills))


def select_agent_team(goal: str) -> list[AgentSpec]:
    """Return a domain-aware agent pack for a project or error goal."""
    low = goal.lower()
    wanted = ['Product Architect Agent', 'Dependency Graph Agent', 'Builder Agent', 'Validator Agent', 'Repair Agent', 'Tester Agent', 'Quality Agent']
    if any(term in low for term in ['tower', 'wave', 'enemy', 'canvas', 'game', 'projectile', 'hud', 'sprite']):
        wanted.insert(1, 'Game Agent')
        wanted.append('Designer Agent')
    elif any(term in low for term in ['crm', 'lead', 'pipeline', 'sales', 'deal', 'account', 'contact']):
        wanted.insert(1, 'CRM Agent')
        wanted.insert(2, 'Data Model Agent')
        wanted.append('Designer Agent')
    elif any(term in low for term in ['saas', 'dashboard', 'admin', 'workspace', 'permission', 'team']):
        wanted.insert(1, 'SaaS Agent')
        wanted.insert(2, 'Data Model Agent')
        wanted.append('Designer Agent')
    elif any(term in low for term in ['data', 'sample', 'model', 'contract', 'entity']):
        wanted.insert(1, 'Data Model Agent')
    elif any(term in low for term in ['design', 'ui', 'layout', 'css']):
        wanted.insert(1, 'Designer Agent')
    agents = list_agents()
    by_name = {agent.name: agent for agent in agents}
    team: list[AgentSpec] = []
    for name in wanted:
        agent = by_name.get(name)
        if agent and agent.agent_id not in {a.agent_id for a in team}:
            team.append(agent)
    return team


def remember_agent_result(agent: AgentSpec, project_id: str, memory: str, success: bool | None = None) -> AgentSpec:
    if project_id not in agent.projects_used:
        agent.projects_used.append(project_id)
    if memory and memory not in agent.memory:
        agent.memory.append(memory[-1500:])
        agent.memory = agent.memory[-80:]
    if success is True:
        agent.success_count += 1
    elif success is False:
        agent.failure_count += 1
    return save_agent(agent)
