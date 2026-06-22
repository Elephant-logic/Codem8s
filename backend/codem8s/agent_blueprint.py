from __future__ import annotations

import json
import re
from typing import Any

from .agent_llm import chat_json
from .deep_game_blueprint import deep_game_blueprint, deep_game_paths, is_deep_game_request
from .models import ProjectSpec


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "generated-app"


def title_from_idea(idea: str) -> str:
    return " ".join(part.capitalize() for part in slug(idea).split("-")) or "Generated App"


def safe_component_name(name: str) -> str:
    raw = re.sub(r"[^a-zA-Z0-9]+", " ", name).title().replace(" ", "")
    return raw or "Generated"


def fallback_app_plan(idea: str, pages: list[str], entities: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "product_positioning": f"A polished, working product for: {idea}",
        "primary_user_flows": ["Open the main screen", "Use real controls", "Mutate state", "Review metrics", "Save or export"],
        "navigation": pages or ["Dashboard", "Items"],
        "dashboard_widgets": ["Key metrics", "Recent activity", "Status breakdown", "Priority work", "Trend summary"],
        "data_model": entities or [{"name": "Item", "fields": ["id", "name", "status", "owner", "updatedAt", "notes"]}],
        "seed_data_requirements": "Use realistic domain-specific data, not placeholder records.",
        "design_system": {"tone": "premium interface", "layout": "responsive app shell", "visuals": ["cards", "badges", "tables", "panels"]},
        "acceptance_criteria": ["No placeholder-only screens", "Real state changes", "Preview loads", "No fake buttons"],
    }


def fallback_blueprint(idea: str) -> dict[str, Any]:
    text = idea.lower()
    if is_deep_game_request(idea):
        return deep_game_blueprint(idea)

    is_game = any(w in text for w in ["game", "snake", "platform", "arcade", "canvas", "puzzle", "tower defense"])
    if is_game:
        pages = ["Main Menu", "Game", "Game Over"]
        bp = {
            "app_name": title_from_idea(idea),
            "goal": idea,
            "kind": "game",
            "runtime": "react-vite-canvas",
            "needs_backend": False,
            "pages": [{"name": p, "purpose": p.lower()} for p in pages],
            "entities": [],
            "systems": [],
            "frontend_files": [],
            "backend_files": [],
            "dependency_topology": {},
            "notes": ["fallback game blueprint"],
        }
        bp["app_plan"] = fallback_app_plan(idea, pages, [])
        return bp

    if "job" in text and any(w in text for w in ["track", "tracker", "application", "applications"]):
        pages = ["Dashboard", "Applications", "Job Details", "Interviews", "Tasks", "Notes", "Analytics", "Settings"]
        entities = [{"name": n, "label": n.title()} for n in ["applications", "interviews", "tasks", "companies", "notes"]]
    elif any(w in text for w in ["crm", "lead", "pipeline", "sales"]):
        pages = ["Dashboard", "Leads", "Pipeline", "Companies", "Tasks", "Analytics"]
        entities = [{"name": n, "label": n.title()} for n in ["leads", "companies", "tasks", "deals"]]
    else:
        pages = ["Dashboard", "Items", "Tasks", "Reports", "Settings"]
        entities = [{"name": "items", "label": "Items"}, {"name": "tasks", "label": "Tasks"}]
    return {
        "app_name": title_from_idea(idea),
        "goal": idea,
        "kind": "business_app",
        "runtime": "react-fastapi-sqlite",
        "needs_backend": True,
        "pages": [{"name": p, "purpose": p.lower()} for p in pages],
        "entities": entities,
        "systems": [{"name": "DashboardAnalytics"}, {"name": "SearchAndFilters"}, {"name": "ActivityTimeline"}],
        "app_plan": fallback_app_plan(idea, pages, entities),
        "frontend_files": [],
        "backend_files": [],
        "dependency_topology": {},
        "notes": ["fallback business blueprint"],
    }


def plan_with_api(idea: str) -> dict[str, Any] | None:
    if is_deep_game_request(idea):
        return deep_game_blueprint(idea)
    system = """
You are Codem8s Product Architect. Return JSON only.
Required keys: app_name, goal, kind, runtime, needs_backend, pages, entities, systems, app_plan, frontend_files, backend_files, dependency_topology, notes.
Plan real products, not placeholder scaffolds.
For games, plan real gameplay systems, entities, UI/HUD, controls, progression, and rendering.
If the user asks for many files, store/entities/systems/components/screens, produce a deep architecture, not a tiny scaffold.
"""
    return chat_json(system, f"Plan this app fully before code generation:\n{idea}", temperature=0.18)


def normalize_blueprint(raw: dict[str, Any] | None, idea: str) -> dict[str, Any]:
    if is_deep_game_request(idea):
        return deep_game_blueprint(idea)
    fallback = fallback_blueprint(idea)
    bp = raw if isinstance(raw, dict) else fallback
    for key, value in fallback.items():
        bp.setdefault(key, value)
    if not isinstance(bp.get("pages"), list) or not bp["pages"]:
        bp["pages"] = fallback["pages"]
    if not isinstance(bp.get("entities"), list):
        bp["entities"] = fallback["entities"]
    pages = [str(p.get("name", p)) if isinstance(p, dict) else str(p) for p in bp.get("pages", [])]
    if not isinstance(bp.get("app_plan"), dict):
        bp["app_plan"] = fallback_app_plan(idea, pages, bp.get("entities") or [])
    else:
        fb_plan = fallback_app_plan(idea, pages, bp.get("entities") or [])
        for key, value in fb_plan.items():
            bp["app_plan"].setdefault(key, value)
    if bp.get("kind") == "game" or bp.get("needs_backend") is False:
        bp["needs_backend"] = False
        if str(bp.get("runtime", "")).lower() in {"unity", "godot"}:
            bp["runtime"] = "react-vite-canvas"
    return bp


def blueprint_from_idea(idea: str, use_api: bool = True) -> dict[str, Any]:
    return normalize_blueprint(plan_with_api(idea) if use_api else None, idea)


def blueprint_from_spec(spec: ProjectSpec) -> dict[str, Any]:
    for entry in reversed(spec.change_log):
        if entry.startswith("BLUEPRINT_JSON:"):
            try:
                return json.loads(entry.removeprefix("BLUEPRINT_JSON:"))
            except json.JSONDecodeError:
                pass
    return blueprint_from_idea(spec.goal, use_api=False)


def add(files: dict[str, str], path: str, purpose: str) -> None:
    if path and isinstance(path, str):
        files[path] = purpose


def topo_role(bp: dict[str, Any], path: str, fallback: str) -> str:
    topo = bp.get("dependency_topology") or {}
    meta = topo.get(path) if isinstance(topo, dict) else None
    app_plan = bp.get("app_plan") if isinstance(bp.get("app_plan"), dict) else {}
    plan_hint = " Product plan: " + json.dumps({"navigation": app_plan.get("navigation"), "dashboard_widgets": app_plan.get("dashboard_widgets"), "data_model": app_plan.get("data_model"), "design_system": app_plan.get("design_system")})[:1200]
    if isinstance(meta, dict):
        return f"{meta.get('role') or fallback}. Topology: imports={meta.get('imports') or []}; exports={meta.get('exports') or []}. Follow this contract exactly.{plan_hint}"
    return fallback + "." + plan_hint


def add_blueprint_requested_files(files: dict[str, str], bp: dict[str, Any]) -> None:
    for path in bp.get("frontend_files") or []:
        if isinstance(path, str):
            if not path.startswith("frontend/"):
                path = "frontend/" + path.lstrip("/")
            add(files, path, topo_role(bp, path, "blueprint requested frontend file"))
    for path in bp.get("backend_files") or []:
        if isinstance(path, str):
            if not path.startswith("backend/"):
                path = "backend/" + path.lstrip("/")
            add(files, path, topo_role(bp, path, "blueprint requested backend file"))


def add_topology_paths(files: dict[str, str], bp: dict[str, Any], paths: list[tuple[str, str, list[str], list[str]]]) -> None:
    topo = bp.setdefault("dependency_topology", {})
    for path, role, imports, exports in paths:
        topo[path] = {"imports": imports, "exports": exports, "role": role}
        add(files, path, topo_role(bp, path, role))


def tower_defense_paths() -> list[tuple[str, str, list[str], list[str]]]:
    return [
        ("frontend/package.json", "frontend package", [], []),
        ("frontend/index.html", "html entry", [], []),
        ("README.md", "instructions", [], []),
        ("frontend/src/styles.css", "polished responsive styles", [], []),
        ("frontend/src/data/towers.js", "tower definitions", [], ["TOWER_TYPES"]),
        ("frontend/src/data/enemies.js", "enemy definitions", [], ["ENEMY_TYPES"]),
        ("frontend/src/data/waves.js", "wave definitions", [], ["WAVES"]),
        ("frontend/src/data/maps.js", "map paths and build zones", [], ["MAPS"]),
        ("frontend/src/utils/math.js", "math helpers", [], ["distance", "clamp", "lerp"]),
        ("frontend/src/entities/Tower.js", "tower entity model", [], ["createTower", "upgradeTower"]),
        ("frontend/src/entities/Enemy.js", "enemy entity model", [], ["createEnemy"]),
        ("frontend/src/systems/EconomySystem.js", "score currency lives economy", [], ["applyReward", "spendCurrency", "loseLife"]),
        ("frontend/src/game/GameCanvas.jsx", "main canvas game scene", [], ["GameCanvas"]),
        ("frontend/src/scenes/MainMenu.jsx", "main menu scene", [], ["MainMenu"]),
        ("frontend/src/App.jsx", "root state router", ["frontend/src/scenes/MainMenu.jsx", "frontend/src/game/GameCanvas.jsx"], ["App"]),
        ("frontend/src/main.jsx", "react entry", ["frontend/src/App.jsx", "frontend/src/styles.css"], []),
    ]


def add_game_architecture_files(files: dict[str, str], bp: dict[str, Any]) -> None:
    spec_text = json.dumps(bp).lower()
    if is_deep_game_request(spec_text):
        add_topology_paths(files, bp, deep_game_paths())
        return
    if "tower defense" in spec_text:
        add_topology_paths(files, bp, tower_defense_paths())
        return
    add_topology_paths(files, bp, [
        ("frontend/package.json", "frontend package", [], []),
        ("frontend/index.html", "html entry", [], []),
        ("README.md", "instructions", [], []),
        ("frontend/src/styles.css", "styles", [], []),
        ("frontend/src/game/constants.js", "game constants", [], ["GAME_WIDTH", "GAME_HEIGHT"]),
        ("frontend/src/game/input.js", "input module", [], ["createInputController"]),
        ("frontend/src/game/collision.js", "collision module", [], ["checkCollision"]),
        ("frontend/src/game/useGameLoop.js", "game loop hook", [], ["useGameLoop"]),
        ("frontend/src/game/GameCanvas.jsx", "main game scene", ["frontend/src/game/useGameLoop.js", "frontend/src/game/input.js", "frontend/src/game/collision.js"], ["GameCanvas"]),
        ("frontend/src/scenes/MainMenu.jsx", "main menu", [], ["MainMenu"]),
        ("frontend/src/scenes/GameOver.jsx", "game over", [], ["GameOver"]),
        ("frontend/src/App.jsx", "root router", ["frontend/src/scenes/MainMenu.jsx", "frontend/src/game/GameCanvas.jsx", "frontend/src/scenes/GameOver.jsx"], ["App"]),
        ("frontend/src/main.jsx", "react entry", ["frontend/src/App.jsx", "frontend/src/styles.css"], []),
    ])


def add_business_architecture_files(files: dict[str, str], bp: dict[str, Any]) -> None:
    paths: list[tuple[str, str, list[str], list[str]]] = [
        ("backend/requirements.txt", "backend dependencies", [], []),
        ("backend/store.py", "persistence and seeded domain data", [], ["store"]),
        ("backend/main.py", "FastAPI application", ["backend/store.py"], ["app"]),
        ("frontend/package.json", "frontend package", [], []),
        ("frontend/index.html", "html entry", [], []),
        ("frontend/src/data/appPlan.js", "saved product plan", [], ["APP_PLAN"]),
        ("frontend/src/data/sampleData.js", "rich sample data", ["frontend/src/data/appPlan.js"], ["sampleData"]),
        ("frontend/src/utils/analytics.js", "metrics helpers", ["frontend/src/data/sampleData.js"], ["getDashboardMetrics", "filterRecords", "groupByStatus"]),
        ("frontend/src/components/Dashboard.jsx", "rich dashboard", [], ["Dashboard"]),
        ("frontend/src/components/EntityPage.jsx", "entity page", [], ["EntityPage"]),
    ]
    for page in bp.get("pages") or []:
        if isinstance(page, dict):
            component = safe_component_name(str(page.get("name", "Page")))
            paths.append((f"frontend/src/pages/{component}.jsx", str(page.get("purpose", "planned page")), ["frontend/src/components/Dashboard.jsx"], [component]))
    paths.extend([
        ("frontend/src/App.jsx", "app shell", [], ["App"]),
        ("frontend/src/main.jsx", "react entry", ["frontend/src/App.jsx", "frontend/src/styles.css"], []),
        ("frontend/src/styles.css", "responsive design system", [], []),
        ("README.md", "instructions", [], []),
    ])
    add_topology_paths(files, bp, paths)


def files_for_blueprint(bp: dict[str, Any]) -> dict[str, str]:
    files: dict[str, str] = {}
    add_blueprint_requested_files(files, bp)
    if bp.get("kind") in {"game", "deep-browser-game"} or bp.get("needs_backend") is False:
        add_game_architecture_files(files, bp)
    else:
        add_business_architecture_files(files, bp)
    return files


def build_spec(idea: str, stack: str = "react-fastapi") -> ProjectSpec:
    bp = blueprint_from_idea(idea, use_api=True)
    files = files_for_blueprint(bp)
    return ProjectSpec(app_name=bp["app_name"], goal=idea, stack=bp.get("runtime", stack), features=["app planner product model", f"kind: {bp.get('kind')}", "dependency topology file plan", "api planned once", "files generated from saved blueprint", "rich design and seed data contract"], files=files, change_log=["BLUEPRINT_JSON:" + json.dumps(bp)])


def apply_instruction(spec: ProjectSpec, instruction: str) -> ProjectSpec:
    bp = blueprint_from_idea(spec.goal + "\nChange request: " + instruction, use_api=True)
    spec.app_name = bp.get("app_name", spec.app_name)
    spec.goal = spec.goal + "\nChange request: " + instruction
    spec.stack = bp.get("runtime", spec.stack)
    spec.features = ["app planner product model", f"kind: {bp.get('kind')}", "dependency topology file plan", "api planned once", "files generated from saved blueprint", "rich design and seed data contract"]
    spec.files = files_for_blueprint(bp)
    spec.change_log.append("INSTRUCTION:" + instruction)
    spec.change_log.append("BLUEPRINT_JSON:" + json.dumps(bp))
    return spec
