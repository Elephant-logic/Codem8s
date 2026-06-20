from __future__ import annotations

import json
import re
from typing import Any

from .models import ProjectSpec
from .agent_llm import chat_json


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "generated-app"


def title_from_idea(idea: str) -> str:
    return " ".join(part.capitalize() for part in slug(idea).split("-")) or "Generated App"


def safe_component_name(name: str) -> str:
    raw = re.sub(r"[^a-zA-Z0-9]+", " ", name).title().replace(" ", "")
    return raw or "Generated"


def fallback_app_plan(idea: str, pages: list[str], entities: list[dict[str, Any]]) -> dict[str, Any]:
    text = idea.lower()
    if "job" in text and any(w in text for w in ["track", "tracker", "application", "applications"]):
        return {
            "product_positioning": "A polished job-search operating system for tracking applications, interviews, tasks, contacts, notes, and momentum.",
            "primary_user_flows": [
                "Review dashboard metrics and urgent next actions",
                "Add or update a job application",
                "Move an application through saved/applied/interview/offer/rejected stages",
                "Open a job detail view with notes, contacts, tasks, and interview timeline",
                "Review analytics by stage, source, company, and week",
            ],
            "navigation": ["Dashboard", "Applications", "Interviews", "Companies", "Tasks", "Notes", "Analytics", "Settings"],
            "dashboard_widgets": ["Pipeline summary", "Upcoming interviews", "Priority tasks", "Application stage chart", "Recent notes", "Weekly activity"],
            "data_model": [
                {"name": "Application", "fields": ["id", "role", "company", "stage", "location", "salary", "source", "appliedDate", "nextStep", "priority", "notes"]},
                {"name": "Interview", "fields": ["id", "applicationId", "type", "date", "contact", "status", "prepNotes"]},
                {"name": "Task", "fields": ["id", "applicationId", "title", "dueDate", "status", "priority"]},
                {"name": "Company", "fields": ["id", "name", "industry", "contact", "rating", "openRoles"]},
            ],
            "seed_data_requirements": "Use realistic companies, roles, dates, salary ranges, stages, contacts, tasks, notes, and interview events.",
            "design_system": {"tone": "premium productivity dashboard", "layout": "sidebar + topbar + responsive cards", "visuals": ["KPI cards", "badges", "tables", "timeline", "charts via CSS bars"]},
            "acceptance_criteria": ["No welcome-only screen", "Dashboard has real metrics", "Applications table/list has actionable rows", "Details and notes feel domain-specific"],
        }
    return {
        "product_positioning": f"A polished application for: {idea}",
        "primary_user_flows": [f"Open {pages[0] if pages else 'Dashboard'}", "Create or update a core record", "Review status and recent activity", "Use search/filter controls"],
        "navigation": pages or ["Dashboard", "Items"],
        "dashboard_widgets": ["Key metrics", "Recent activity", "Status breakdown", "Priority work", "Trend summary"],
        "data_model": entities or [{"name": "Item", "fields": ["id", "name", "status", "owner", "updatedAt", "notes"]}],
        "seed_data_requirements": "Use realistic domain-specific data, not placeholder records.",
        "design_system": {"tone": "premium SaaS dashboard", "layout": "sidebar + responsive content cards", "visuals": ["KPI cards", "badges", "tables", "panels"]},
        "acceptance_criteria": ["No generic welcome page", "Real seeded data", "Useful dashboard", "Responsive polished UI"],
    }


def fallback_blueprint(idea: str) -> dict[str, Any]:
    text = idea.lower()
    is_game = any(w in text for w in ["game", "snake", "platform", "arcade", "canvas", "puzzle", "tower defense"])
    if is_game:
        pages = ["Main Menu", "Game", "Game Over"]
        bp = {
            "app_name": title_from_idea(idea),
            "goal": idea,
            "kind": "game",
            "runtime": "react-vite-canvas",
            "needs_backend": False,
            "pages": [{"name": "Main Menu", "purpose": "start/options"}, {"name": "Game", "purpose": "playable scene"}, {"name": "Game Over", "purpose": "restart/final score"}],
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
        entities = [
            {"name": "applications", "label": "Applications"},
            {"name": "interviews", "label": "Interviews"},
            {"name": "tasks", "label": "Tasks"},
            {"name": "companies", "label": "Companies"},
            {"name": "notes", "label": "Notes"},
        ]
    elif any(w in text for w in ["crm", "lead", "pipeline", "sales"]):
        pages = ["Dashboard", "Leads", "Pipeline", "Companies", "Tasks", "Analytics"]
        entities = [{"name": "leads", "label": "Leads"}, {"name": "companies", "label": "Companies"}, {"name": "tasks", "label": "Tasks"}, {"name": "deals", "label": "Deals"}]
    elif any(w in text for w in ["booking", "appointment", "reservation", "calendar"]):
        pages = ["Dashboard", "Appointments", "Calendar", "Customers", "Services", "Reports"]
        entities = [{"name": "appointments", "label": "Appointments"}, {"name": "customers", "label": "Customers"}, {"name": "services", "label": "Services"}, {"name": "staff", "label": "Staff"}]
    elif any(w in text for w in ["inventory", "stock", "warehouse", "sku"]):
        pages = ["Dashboard", "Products", "Stock", "Suppliers", "Movements", "Reports"]
        entities = [{"name": "products", "label": "Products"}, {"name": "suppliers", "label": "Suppliers"}, {"name": "movements", "label": "Movements"}, {"name": "locations", "label": "Locations"}]
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
        "systems": [
            {"name": "DashboardAnalytics", "description": "computes metrics, trends, and status breakdowns"},
            {"name": "SearchAndFilters", "description": "filters lists by status, text, owner, and date"},
            {"name": "ActivityTimeline", "description": "recent changes and next actions"},
        ],
        "app_plan": fallback_app_plan(idea, pages, entities),
        "frontend_files": [],
        "backend_files": [],
        "dependency_topology": {},
        "notes": ["fallback business blueprint with app_plan"],
    }


def plan_with_api(idea: str) -> dict[str, Any] | None:
    system = """
You are Codem8s Product Architect. Return JSON only.
Think like a senior product designer + software architect before code generation.
Do not default to CRUD. Do not make a random file list. Do not make a welcome-screen app.

Required top-level keys:
app_name, goal, kind, runtime, needs_backend, pages, entities, systems, app_plan, frontend_files, backend_files, dependency_topology, notes.

app_plan is mandatory and must include:
{
  "product_positioning": "what this product is and who it serves",
  "primary_user_flows": ["5-8 real user flows"],
  "navigation": ["actual nav items"],
  "dashboard_widgets": ["specific dashboard widgets"],
  "data_model": [{"name":"Entity", "fields":["real fields"]}],
  "seed_data_requirements": "what rich sample data must exist",
  "design_system": {"tone":"...", "layout":"...", "visuals":["..."]},
  "acceptance_criteria": ["how to know generated app is not shallow"]
}

For business apps, plan a product that feels complete:
- dashboards with KPIs, tables/lists, recent activity, status breakdowns, charts/bars, and next actions
- entity pages with domain-specific fields and detail panels
- realistic seeded data requirements
- navigation and layout
- meaningful backend resources if needed

For games, plan real gameplay systems, levels/waves, entities, UI/HUD, controls, and progression.

Dependency topology must be a map:
{
  "file/path.js": {
    "imports": ["other/file.js"],
    "exports": ["nameOne", "nameTwo"],
    "role": "plain description"
  }
}

Rules:
- Browser games should use react-vite-canvas or react-vite-webgl, not Unity/Godot.
- .js files are plain modules only.
- .jsx files are UI/scene/component files only.
- Plan leaves first: data/utils/entities -> systems -> modules -> UI -> pages/scenes -> App.
- Every planned UI should have a purpose from app_plan.
"""
    return chat_json(system, f"Plan this app fully before code generation:\n{idea}", temperature=0.18)


def normalize_blueprint(raw: dict[str, Any] | None, idea: str) -> dict[str, Any]:
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
    plan_hint = " Product plan: " + json.dumps({
        "navigation": app_plan.get("navigation"),
        "dashboard_widgets": app_plan.get("dashboard_widgets"),
        "data_model": app_plan.get("data_model"),
        "design_system": app_plan.get("design_system"),
    })[:1200]
    if isinstance(meta, dict):
        imports = meta.get("imports") or []
        exports = meta.get("exports") or []
        role = meta.get("role") or fallback
        return f"{role}. Topology: imports={imports}; exports={exports}. Follow this contract exactly.{plan_hint}"
    return fallback + "." + plan_hint


def add_blueprint_requested_files(files: dict[str, str], bp: dict[str, Any]) -> None:
    for path in bp.get("frontend_files") or []:
        if isinstance(path, str) and path.startswith("frontend/"):
            add(files, path, topo_role(bp, path, "blueprint requested frontend file"))
    for path in bp.get("backend_files") or []:
        if isinstance(path, str) and path.startswith("backend/"):
            add(files, path, topo_role(bp, path, "blueprint requested backend file"))


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
        ("frontend/src/utils/path.js", "path helpers", ["frontend/src/utils/math.js"], ["pointOnPath", "advanceAlongPath"]),
        ("frontend/src/entities/Tower.js", "tower entity model", ["frontend/src/data/towers.js"], ["createTower", "upgradeTower"]),
        ("frontend/src/entities/Enemy.js", "enemy entity model", ["frontend/src/data/enemies.js"], ["createEnemy"]),
        ("frontend/src/entities/Projectile.js", "projectile entity model", [], ["createProjectile"]),
        ("frontend/src/entities/Wave.js", "wave model", ["frontend/src/data/waves.js"], ["getWave"]),
        ("frontend/src/systems/PathSystem.js", "waypoint movement system", ["frontend/src/utils/path.js"], ["updateEnemyPath"]),
        ("frontend/src/systems/EconomySystem.js", "score currency lives economy", [], ["applyReward", "spendCurrency", "loseLife"]),
        ("frontend/src/systems/UpgradeSystem.js", "tower upgrade rules", ["frontend/src/entities/Tower.js", "frontend/src/systems/EconomySystem.js"], ["canUpgrade", "applyUpgrade"]),
        ("frontend/src/systems/PlacementSystem.js", "click placement validation", ["frontend/src/data/maps.js", "frontend/src/entities/Tower.js", "frontend/src/utils/math.js"], ["canPlaceTower", "placeTower"]),
        ("frontend/src/systems/CombatSystem.js", "tower targeting and damage", ["frontend/src/utils/math.js", "frontend/src/entities/Projectile.js"], ["updateCombat"]),
        ("frontend/src/systems/WaveManager.js", "wave spawning and progression", ["frontend/src/entities/Enemy.js", "frontend/src/entities/Wave.js"], ["createWaveState", "updateWave"]),
        ("frontend/src/systems/ParticleSystem.js", "hit and explosion particles", [], ["createHitParticle", "updateParticles"]),
        ("frontend/src/game/constants.js", "game constants", [], ["GAME_WIDTH", "GAME_HEIGHT", "TICK_RATE"]),
        ("frontend/src/game/collision.js", "collision and hit testing", ["frontend/src/utils/math.js"], ["circleHit", "pointInRect"]),
        ("frontend/src/game/input.js", "keyboard pointer input", [], ["createInputController"]),
        ("frontend/src/game/audio.js", "audio helpers", [], ["playSound"]),
        ("frontend/src/game/gameState.js", "initial game state and reducers", ["frontend/src/data/maps.js"], ["createInitialGameState"]),
        ("frontend/src/game/useGameLoop.js", "requestAnimationFrame loop hook", [], ["useGameLoop"]),
        ("frontend/src/game/rendering.js", "canvas rendering helpers", ["frontend/src/game/constants.js"], ["renderGame"]),
        ("frontend/src/ui/Button.jsx", "reusable button", [], ["Button"]),
        ("frontend/src/ui/Hud.jsx", "score lives currency HUD", [], ["Hud"]),
        ("frontend/src/ui/TowerPalette.jsx", "tower selector", ["frontend/src/data/towers.js"], ["TowerPalette"]),
        ("frontend/src/ui/UpgradePanel.jsx", "selected tower upgrades", ["frontend/src/systems/UpgradeSystem.js"], ["UpgradePanel"]),
        ("frontend/src/ui/WavePanel.jsx", "wave status controls", [], ["WavePanel"]),
        ("frontend/src/ui/GameStats.jsx", "score wave lives display", [], ["GameStats"]),
        ("frontend/src/game/GameCanvas.jsx", "main canvas game scene", ["frontend/src/game/gameState.js", "frontend/src/game/useGameLoop.js", "frontend/src/game/rendering.js", "frontend/src/systems/WaveManager.js", "frontend/src/systems/PathSystem.js", "frontend/src/systems/CombatSystem.js", "frontend/src/systems/PlacementSystem.js", "frontend/src/systems/UpgradeSystem.js", "frontend/src/ui/Hud.jsx", "frontend/src/ui/TowerPalette.jsx", "frontend/src/ui/UpgradePanel.jsx", "frontend/src/ui/WavePanel.jsx"], ["GameCanvas"]),
        ("frontend/src/scenes/MainMenu.jsx", "main menu scene", ["frontend/src/ui/Button.jsx"], ["MainMenu"]),
        ("frontend/src/scenes/GameScene.jsx", "playable game scene wrapper", ["frontend/src/game/GameCanvas.jsx"], ["GameScene"]),
        ("frontend/src/scenes/GameOver.jsx", "game over scene", ["frontend/src/ui/Button.jsx"], ["GameOver"]),
        ("frontend/src/App.jsx", "root state router", ["frontend/src/scenes/MainMenu.jsx", "frontend/src/scenes/GameScene.jsx", "frontend/src/scenes/GameOver.jsx"], ["App"]),
        ("frontend/src/main.jsx", "react entry", ["frontend/src/App.jsx", "frontend/src/styles.css"], []),
    ]


def add_topology_paths(files: dict[str, str], bp: dict[str, Any], paths: list[tuple[str, str, list[str], list[str]]]) -> None:
    topo = bp.setdefault("dependency_topology", {})
    for path, role, imports, exports in paths:
        topo[path] = {"imports": imports, "exports": exports, "role": role}
        add(files, path, topo_role(bp, path, role))


def add_game_architecture_files(files: dict[str, str], bp: dict[str, Any]) -> None:
    goal = str(bp.get("goal", "")).lower()
    spec_text = json.dumps(bp).lower()
    if "tower defense" in goal or "tower defense" in spec_text:
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
        ("backend/store.py", "SQLite/in-memory persistence and seeded domain data", [], ["store"]),
        ("backend/main.py", "FastAPI application exposing domain resources and dashboard summary", ["backend/store.py"], ["app"]),
        ("frontend/package.json", "frontend package", [], []),
        ("frontend/index.html", "html entry", [], []),
        ("frontend/src/data/appPlan.js", "saved product plan, navigation, dashboard widgets, seed-data contract, design-system tokens", [], ["APP_PLAN"]),
        ("frontend/src/data/sampleData.js", "rich realistic sample data derived from app_plan", ["frontend/src/data/appPlan.js"], ["sampleData"]),
        ("frontend/src/utils/analytics.js", "dashboard metrics, trends, filtering, grouping helpers", ["frontend/src/data/sampleData.js"], ["getDashboardMetrics", "filterRecords", "groupByStatus"]),
        ("frontend/src/api/client.js", "API client with graceful sample-data fallback", ["frontend/src/data/sampleData.js"], ["api"]),
        ("frontend/src/ui/Card.jsx", "premium reusable card component", [], ["Card"]),
        ("frontend/src/ui/Modal.jsx", "modal UI component", [], ["Modal"]),
        ("frontend/src/ui/StatusPill.jsx", "status badge component", [], ["StatusPill"]),
        ("frontend/src/components/Nav.jsx", "sidebar/top navigation from app_plan", ["frontend/src/data/appPlan.js"], ["Nav"]),
        ("frontend/src/components/Dashboard.jsx", "rich dashboard with KPI cards, activity, status breakdowns, and next actions", ["frontend/src/data/appPlan.js", "frontend/src/data/sampleData.js", "frontend/src/utils/analytics.js", "frontend/src/ui/Card.jsx", "frontend/src/ui/StatusPill.jsx"], ["Dashboard"]),
        ("frontend/src/components/EntityPage.jsx", "reusable entity list/detail page with search, filters, table/cards", ["frontend/src/data/sampleData.js", "frontend/src/utils/analytics.js", "frontend/src/ui/Card.jsx", "frontend/src/ui/StatusPill.jsx"], ["EntityPage"]),
        ("frontend/src/components/FormBuilder.jsx", "dynamic domain form builder", ["frontend/src/ui/Card.jsx"], ["FormBuilder"]),
    ]
    for page in bp.get("pages") or []:
        if isinstance(page, dict):
            component = safe_component_name(str(page.get("name", "Page")))
            paths.append((f"frontend/src/pages/{component}.jsx", str(page.get("purpose", "planned page")), ["frontend/src/components/Dashboard.jsx", "frontend/src/components/EntityPage.jsx", "frontend/src/data/appPlan.js"], [component]))
    for entity in bp.get("entities") or []:
        if isinstance(entity, dict):
            name = safe_component_name(str(entity.get("name", "Entity")))
            paths.append((f"frontend/src/entities/{name}.js", str(entity.get("label", "entity model")), ["frontend/src/data/appPlan.js"], [f"create{name}", f"{name}Schema"] ))
            paths.append((f"backend/routes/{name.lower()}.py", f"API routes for {name}", ["backend/store.py"], ["router"] ))
    page_imports = [p for p, *_ in paths if p.startswith("frontend/src/pages/")]
    paths.extend([
        ("frontend/src/App.jsx", "app shell tying navigation, pages, dashboard, sample data, and product plan together", ["frontend/src/data/appPlan.js", "frontend/src/components/Nav.jsx", *page_imports], ["App"]),
        ("frontend/src/main.jsx", "react entry", ["frontend/src/App.jsx", "frontend/src/styles.css"], []),
        ("frontend/src/styles.css", "premium responsive design system and dashboard styling", [], []),
        ("README.md", "instructions and product overview", [], []),
    ])
    add_topology_paths(files, bp, paths)


def files_for_blueprint(bp: dict[str, Any]) -> dict[str, str]:
    files: dict[str, str] = {}
    add_blueprint_requested_files(files, bp)
    if bp.get("kind") == "game" or bp.get("needs_backend") is False:
        add_game_architecture_files(files, bp)
    else:
        add_business_architecture_files(files, bp)
    return files


def build_spec(idea: str, stack: str = "react-fastapi") -> ProjectSpec:
    bp = blueprint_from_idea(idea, use_api=True)
    files = files_for_blueprint(bp)
    return ProjectSpec(
        app_name=bp["app_name"],
        goal=idea,
        stack=bp.get("runtime", stack),
        features=["app planner product model", f"kind: {bp.get('kind')}", "dependency topology file plan", "api planned once", "files generated from saved blueprint", "rich design and seed data contract"],
        files=files,
        change_log=["BLUEPRINT_JSON:" + json.dumps(bp)],
    )


def apply_instruction(spec: ProjectSpec, instruction: str) -> ProjectSpec:
    bp = blueprint_from_idea(spec.goal + "\nChange request: " + instruction, use_api=True)
    spec.features = ["app planner product model", f"kind: {bp.get('kind')}", "dependency topology file plan", "api planned once", "files generated from saved blueprint", "rich design and seed data contract"]
    spec.files = files_for_blueprint(bp)
    spec.change_log.append("INSTRUCTION:" + instruction)
    spec.change_log.append("BLUEPRINT_JSON:" + json.dumps(bp))
    return spec
