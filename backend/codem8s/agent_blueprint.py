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


def fallback_blueprint(idea: str) -> dict[str, Any]:
    text = idea.lower()
    is_game = any(w in text for w in ["game", "snake", "platform", "arcade", "canvas", "puzzle", "tower defense"])
    if is_game:
        return {
            "app_name": title_from_idea(idea),
            "goal": idea,
            "kind": "game",
            "runtime": "react-vite-canvas",
            "needs_backend": False,
            "pages": [
                {"name": "Main Menu", "purpose": "start/options"},
                {"name": "Game", "purpose": "playable scene"},
                {"name": "Game Over", "purpose": "restart/final score"},
            ],
            "entities": [],
            "systems": [],
            "frontend_files": [],
            "backend_files": [],
            "dependency_topology": {},
            "notes": ["fallback game blueprint"],
        }

    if any(w in text for w in ["crm", "lead", "pipeline", "sales"]):
        pages = ["Dashboard", "Leads", "Pipeline", "Companies", "Tasks"]
        entities = [
            {"name": "leads", "label": "Leads"},
            {"name": "companies", "label": "Companies"},
            {"name": "tasks", "label": "Tasks"},
        ]
    elif any(w in text for w in ["booking", "appointment", "reservation", "calendar"]):
        pages = ["Dashboard", "Appointments", "Calendar", "Customers", "Services"]
        entities = [
            {"name": "appointments", "label": "Appointments"},
            {"name": "customers", "label": "Customers"},
            {"name": "services", "label": "Services"},
        ]
    elif any(w in text for w in ["inventory", "stock", "warehouse", "sku"]):
        pages = ["Dashboard", "Products", "Stock", "Suppliers", "Movements"]
        entities = [
            {"name": "products", "label": "Products"},
            {"name": "suppliers", "label": "Suppliers"},
            {"name": "movements", "label": "Movements"},
        ]
    else:
        pages = ["Dashboard", "Items"]
        entities = [{"name": "items", "label": "Items"}]

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
        "dependency_topology": {},
        "notes": ["fallback business blueprint"],
    }


def plan_with_api(idea: str) -> dict[str, Any] | None:
    system = """
You are Codem8s Planner. Return JSON only.
Think like an architect before code generation.
Do not default to CRUD.
Do not make a random file list.

Required keys:
app_name, goal, kind, runtime, needs_backend, pages, entities, systems, frontend_files, backend_files, dependency_topology, notes.

dependency_topology must be a map:
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
- Plan leaves first: data/utils/entities -> systems -> game modules -> UI -> scenes -> App.
"""
    return chat_json(system, f"Plan this app fully before code generation:\n{idea}", temperature=0.2)


def normalize_blueprint(raw: dict[str, Any] | None, idea: str) -> dict[str, Any]:
    fallback = fallback_blueprint(idea)
    bp = raw if isinstance(raw, dict) else fallback
    for key, value in fallback.items():
        bp.setdefault(key, value)
    if not isinstance(bp.get("pages"), list) or not bp["pages"]:
        bp["pages"] = fallback["pages"]
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
    if isinstance(meta, dict):
        imports = meta.get("imports") or []
        exports = meta.get("exports") or []
        role = meta.get("role") or fallback
        return f"{role}. Topology: imports={imports}; exports={exports}. Follow this contract exactly."
    return fallback


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
    add(files, "backend/requirements.txt", "backend dependencies")
    add(files, "backend/store.py", "SQLite persistence")
    add(files, "backend/main.py", "FastAPI application")
    add(files, "frontend/package.json", "frontend package")
    add(files, "frontend/index.html", "html entry")
    add(files, "frontend/src/api/client.js", "API client")
    add(files, "frontend/src/ui/Card.jsx", "card UI component")
    add(files, "frontend/src/ui/Modal.jsx", "modal UI component")
    add(files, "frontend/src/ui/StatusPill.jsx", "status display component")
    add(files, "frontend/src/components/FormBuilder.jsx", "dynamic form builder")
    add(files, "frontend/src/components/Dashboard.jsx", "dashboard")
    add(files, "frontend/src/components/EntityPage.jsx", "entity page")
    add(files, "frontend/src/components/Nav.jsx", "navigation")
    for page in bp.get("pages") or []:
        if isinstance(page, dict):
            add(files, f"frontend/src/pages/{safe_component_name(str(page.get('name', 'Page')))}.jsx", str(page.get("purpose", "planned page")))
    for entity in bp.get("entities") or []:
        if isinstance(entity, dict):
            name = safe_component_name(str(entity.get("name", "Entity")))
            add(files, f"frontend/src/entities/{name}.js", str(entity.get("label", "entity model")))
            add(files, f"backend/routes/{name.lower()}.py", f"API routes for {name}")
    add(files, "frontend/src/App.jsx", "app shell")
    add(files, "frontend/src/main.jsx", "react entry")
    add(files, "frontend/src/styles.css", "styles")
    add(files, "README.md", "instructions")


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
        features=["agent planned blueprint", f"kind: {bp.get('kind')}", "dependency topology file plan", "api planned once", "files generated from saved blueprint"],
        files=files,
        change_log=["BLUEPRINT_JSON:" + json.dumps(bp)],
    )


def apply_instruction(spec: ProjectSpec, instruction: str) -> ProjectSpec:
    bp = blueprint_from_idea(spec.goal + "\nChange request: " + instruction, use_api=True)
    spec.features = ["agent replanned blueprint", f"kind: {bp.get('kind')}", "dependency topology file plan", "api planned once", "files generated from saved blueprint"]
    spec.files = files_for_blueprint(bp)
    spec.change_log.append("INSTRUCTION:" + instruction)
    spec.change_log.append("BLUEPRINT_JSON:" + json.dumps(bp))
    return spec
