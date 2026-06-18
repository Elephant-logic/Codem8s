from __future__ import annotations
import json, re
from typing import Any
from .models import ProjectSpec
from .agent_llm import chat_json


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "generated-app"


def title_from_idea(idea: str) -> str:
    return " ".join(part.capitalize() for part in slug(idea).split("-")) or "Generated App"


def fallback_blueprint(idea: str) -> dict[str, Any]:
    text = idea.lower()
    if any(w in text for w in ["game", "snake", "platform", "arcade", "canvas", "puzzle", "tower defense"]):
        pages = [
            {"name": "Main Menu", "purpose": "start and options"},
            {"name": "Game", "purpose": "playable game scene"},
            {"name": "Game Over", "purpose": "final score and restart"},
        ]
        return {
            "app_name": title_from_idea(idea),
            "goal": idea,
            "kind": "game",
            "runtime": "react-vite-canvas",
            "needs_backend": False,
            "pages": pages,
            "entities": [],
            "systems": [],
            "frontend_files": [],
            "backend_files": [],
            "notes": ["fallback game blueprint"],
        }

    if any(w in text for w in ["crm", "lead", "pipeline", "sales"]):
        entities = [
            {"name": "leads", "label": "Leads", "fields": [
                {"name": "name", "label": "Lead name", "type": "text", "required": True},
                {"name": "company", "label": "Company", "type": "text"},
                {"name": "email", "label": "Email", "type": "email"},
                {"name": "stage", "label": "Stage", "type": "select", "options": ["lead", "contacted", "proposal", "won", "lost"]},
                {"name": "next_action", "label": "Next action", "type": "text"},
                {"name": "notes", "label": "Notes", "type": "textarea"}]},
            {"name": "companies", "label": "Companies", "fields": [
                {"name": "name", "label": "Company", "type": "text", "required": True},
                {"name": "contact", "label": "Contact", "type": "text"},
                {"name": "status", "label": "Status", "type": "select", "options": ["prospect", "active", "lost"]}]},
            {"name": "tasks", "label": "Tasks", "fields": [
                {"name": "title", "label": "Task", "type": "text", "required": True},
                {"name": "due", "label": "Due", "type": "date"},
                {"name": "status", "label": "Status", "type": "select", "options": ["todo", "doing", "done"]}]},
        ]
        pages = ["Dashboard", "Leads", "Pipeline", "Companies", "Tasks"]
    elif any(w in text for w in ["booking", "appointment", "reservation", "calendar"]):
        entities = [
            {"name": "appointments", "label": "Appointments", "fields": [
                {"name": "customer", "label": "Customer", "type": "text", "required": True},
                {"name": "service", "label": "Service", "type": "text", "required": True},
                {"name": "date", "label": "Date", "type": "date"},
                {"name": "status", "label": "Status", "type": "select", "options": ["booked", "confirmed", "completed", "cancelled"]}]},
            {"name": "customers", "label": "Customers", "fields": [
                {"name": "name", "label": "Name", "type": "text", "required": True},
                {"name": "phone", "label": "Phone", "type": "text"},
                {"name": "email", "label": "Email", "type": "email"}]},
            {"name": "services", "label": "Services", "fields": [
                {"name": "name", "label": "Service", "type": "text", "required": True},
                {"name": "duration", "label": "Duration", "type": "text"},
                {"name": "price", "label": "Price", "type": "number"}]},
        ]
        pages = ["Dashboard", "Appointments", "Calendar", "Customers", "Services"]
    elif any(w in text for w in ["inventory", "stock", "warehouse", "sku"]):
        entities = [
            {"name": "products", "label": "Products", "fields": [
                {"name": "product", "label": "Product", "type": "text", "required": True},
                {"name": "sku", "label": "SKU", "type": "text"},
                {"name": "quantity", "label": "Quantity", "type": "number"},
                {"name": "status", "label": "Stock state", "type": "select", "options": ["in_stock", "low", "ordered", "discontinued"]}]},
            {"name": "suppliers", "label": "Suppliers", "fields": [
                {"name": "name", "label": "Supplier", "type": "text", "required": True},
                {"name": "contact", "label": "Contact", "type": "text"}]},
            {"name": "movements", "label": "Movements", "fields": [
                {"name": "product", "label": "Product", "type": "text", "required": True},
                {"name": "change", "label": "Quantity change", "type": "number"},
                {"name": "reason", "label": "Reason", "type": "text"}]},
        ]
        pages = ["Dashboard", "Products", "Stock", "Suppliers", "Movements"]
    else:
        entities = [{"name": "items", "label": "Items", "fields": [
            {"name": "title", "label": "Title", "type": "text", "required": True},
            {"name": "status", "label": "Status", "type": "select", "options": ["active", "paused", "done"]},
            {"name": "notes", "label": "Notes", "type": "textarea"}]}]
        pages = ["Dashboard", "Items"]

    return {
        "app_name": title_from_idea(idea),
        "goal": idea,
        "kind": "business_app",
        "runtime": "react-fastapi-sqlite",
        "needs_backend": True,
        "pages": [{"name": p, "purpose": p.lower()} for p in pages],
        "entities": entities,
        "frontend_files": [],
        "backend_files": [],
        "notes": ["fallback business blueprint"],
    }


def plan_with_api(idea: str) -> dict[str, Any] | None:
    system = """
You are Codem8s Planner. Return JSON only. Think first. Do not default to CRUD.
Plan architecture, pages, entities, systems, workflows, and files.

Important:
- Do not plan Unity/Godot unless the output files are actually Unity/Godot files.
- For browser games use runtime react-vite-canvas or react-vite-webgl.
- For large games/tools, include many files in frontend_files/backend_files, not a tiny skeleton.
- Required keys: app_name, goal, kind, runtime, needs_backend, pages, entities, systems, frontend_files, backend_files, notes.
"""
    return chat_json(system, f"Plan this app fully before code generation:\n{idea}", temperature=0.2)


def normalize_blueprint(raw: dict[str, Any] | None, idea: str) -> dict[str, Any]:
    fallback = fallback_blueprint(idea)
    bp = raw if isinstance(raw, dict) else fallback
    for k, v in fallback.items():
        bp.setdefault(k, v)
    if not isinstance(bp.get("pages"), list) or not bp["pages"]:
        bp["pages"] = fallback["pages"]
    if bp.get("kind") != "game" and (not isinstance(bp.get("entities"), list) or not bp["entities"]):
        bp["entities"] = fallback["entities"]
    if bp.get("kind") == "game" or bp.get("needs_backend") is False:
        bp["needs_backend"] = False
        if str(bp.get("runtime", "")).lower() in {"unity", "godot"}:
            bp["runtime"] = "react-vite-canvas"
    return bp


def blueprint_from_idea(idea: str, use_api: bool = True) -> dict[str, Any]:
    raw = plan_with_api(idea) if use_api else None
    return normalize_blueprint(raw, idea)


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


def safe_component_name(name: str) -> str:
    raw = re.sub(r"[^a-zA-Z0-9]+", " ", name).title().replace(" ", "")
    return raw or "Generated"


def add_blueprint_requested_files(files: dict[str, str], bp: dict[str, Any]) -> None:
    for path in bp.get("frontend_files") or []:
        if isinstance(path, str) and path.startswith("frontend/"):
            add(files, path, "blueprint requested frontend file")
    for path in bp.get("backend_files") or []:
        if isinstance(path, str) and path.startswith("backend/"):
            add(files, path, "blueprint requested backend file")


def add_game_architecture_files(files: dict[str, str], bp: dict[str, Any]) -> None:
    goal = str(bp.get("goal", "")).lower()
    spec_text = json.dumps(bp).lower()

    add(files, "frontend/src/App.jsx", "game app shell and state routing")
    add(files, "frontend/src/styles.css", "polished game styling")
    add(files, "frontend/src/game/GameCanvas.jsx", "main canvas game scene")
    add(files, "frontend/src/game/useGameLoop.js", "requestAnimationFrame game loop")
    add(files, "frontend/src/game/input.js", "keyboard pointer input")
    add(files, "frontend/src/game/collision.js", "collision and hit testing")
    add(files, "frontend/src/game/gameState.js", "initial game state and reducers")
    add(files, "frontend/src/game/constants.js", "game constants and balancing")
    add(files, "frontend/src/game/rendering.js", "canvas rendering helpers")
    add(files, "frontend/src/game/audio.js", "audio and sound helpers")

    add(files, "frontend/src/scenes/MainMenu.jsx", "main menu scene")
    add(files, "frontend/src/scenes/GameScene.jsx", "playable game scene wrapper")
    add(files, "frontend/src/scenes/GameOver.jsx", "game over and restart scene")
    add(files, "frontend/src/ui/Hud.jsx", "score lives currency HUD")
    add(files, "frontend/src/ui/Button.jsx", "reusable polished button")

    if "tower defense" in goal or "tower defense" in spec_text:
        tower_files = {
            "frontend/src/entities/Tower.js": "tower entity model and upgrades",
            "frontend/src/entities/Enemy.js": "enemy entity model",
            "frontend/src/entities/Projectile.js": "projectile entity model",
            "frontend/src/entities/Wave.js": "wave definition model",
            "frontend/src/systems/WaveManager.js": "wave spawning and progression",
            "frontend/src/systems/PathSystem.js": "waypoint path movement",
            "frontend/src/systems/CombatSystem.js": "tower targeting and damage",
            "frontend/src/systems/EconomySystem.js": "currency score lives economy",
            "frontend/src/systems/UpgradeSystem.js": "tower upgrade rules",
            "frontend/src/systems/PlacementSystem.js": "click to place tower validation",
            "frontend/src/systems/ParticleSystem.js": "hit and explosion particles",
            "frontend/src/ui/TowerPalette.jsx": "tower selection palette",
            "frontend/src/ui/UpgradePanel.jsx": "selected tower upgrades",
            "frontend/src/ui/WavePanel.jsx": "wave status controls",
            "frontend/src/ui/GameStats.jsx": "score wave lives display",
            "frontend/src/data/towers.js": "tower definitions",
            "frontend/src/data/enemies.js": "enemy definitions",
            "frontend/src/data/waves.js": "wave definitions",
            "frontend/src/data/maps.js": "map paths and build zones",
            "frontend/src/utils/math.js": "math helpers",
            "frontend/src/utils/path.js": "path helpers",
        }
        for path, purpose in tower_files.items():
            add(files, path, purpose)

    elif "snake" in goal or "snake" in spec_text:
        snake_files = {
            "frontend/src/entities/Snake.js": "snake body model",
            "frontend/src/entities/Food.js": "food spawning model",
            "frontend/src/systems/SnakeSystem.js": "snake movement growth collision",
            "frontend/src/systems/ScoreSystem.js": "score and high score",
            "frontend/src/ui/ScoreBoard.jsx": "snake score display",
        }
        for path, purpose in snake_files.items():
            add(files, path, purpose)

    else:
        for system in bp.get("systems") or []:
            if isinstance(system, dict):
                name = safe_component_name(str(system.get("name", "System")))
                add(files, f"frontend/src/systems/{name}.js", str(system.get("purpose", "planned system")))


def add_business_architecture_files(files: dict[str, str], bp: dict[str, Any]) -> None:
    add(files, "backend/main.py", "FastAPI application")
    add(files, "backend/store.py", "SQLite persistence")
    add(files, "backend/requirements.txt", "backend dependencies")
    add(files, "frontend/src/components/Nav.jsx", "navigation")
    add(files, "frontend/src/components/Dashboard.jsx", "dashboard")
    add(files, "frontend/src/components/EntityPage.jsx", "entity page")
    add(files, "frontend/src/components/FormBuilder.jsx", "dynamic form builder")
    add(files, "frontend/src/api/client.js", "API client")
    add(files, "frontend/src/ui/Card.jsx", "card UI component")
    add(files, "frontend/src/ui/Modal.jsx", "modal UI component")
    add(files, "frontend/src/ui/StatusPill.jsx", "status display component")

    for page in bp.get("pages") or []:
        if isinstance(page, dict):
            name = safe_component_name(str(page.get("name", "Page")))
            add(files, f"frontend/src/pages/{name}.jsx", str(page.get("purpose", "planned page")))

    for entity in bp.get("entities") or []:
        if isinstance(entity, dict):
            name = safe_component_name(str(entity.get("name", "Entity")))
            add(files, f"frontend/src/entities/{name}.js", str(entity.get("label", "entity model")))
            add(files, f"backend/routes/{name.lower()}.py", f"API routes for {name}")


def files_for_blueprint(bp: dict[str, Any]) -> dict[str, str]:
    files: dict[str, str] = {
        "frontend/package.json": "frontend package",
        "frontend/index.html": "html entry",
        "frontend/src/main.jsx": "react entry",
        "frontend/src/App.jsx": "app shell",
        "frontend/src/styles.css": "styles",
        "README.md": "instructions",
    }

    add_blueprint_requested_files(files, bp)

    if bp.get("kind") == "game" or bp.get("needs_backend") is False:
        add_game_architecture_files(files, bp)
        return files

    add_business_architecture_files(files, bp)
    return files


def build_spec(idea: str, stack: str = "react-fastapi") -> ProjectSpec:
    bp = blueprint_from_idea(idea, use_api=True)
    return ProjectSpec(
        app_name=bp["app_name"],
        goal=idea,
        stack=bp.get("runtime", stack),
        features=[
            "agent planned blueprint",
            f"kind: {bp.get('kind')}",
            "expanded architecture file plan",
            "api planned once",
            "files generated from saved blueprint",
        ],
        files=files_for_blueprint(bp),
        change_log=["BLUEPRINT_JSON:" + json.dumps(bp)],
    )


def apply_instruction(spec: ProjectSpec, instruction: str) -> ProjectSpec:
    bp = blueprint_from_idea(spec.goal + "\nChange request: " + instruction, use_api=True)
    spec.features = [
        "agent replanned blueprint",
        f"kind: {bp.get('kind')}",
        "expanded architecture file plan",
        "api planned once",
        "files generated from saved blueprint",
    ]
    spec.files = files_for_blueprint(bp)
    spec.change_log.append("INSTRUCTION:" + instruction)
    spec.change_log.append("BLUEPRINT_JSON:" + json.dumps(bp))
    return spec
