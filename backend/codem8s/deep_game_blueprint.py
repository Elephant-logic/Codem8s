from __future__ import annotations

from typing import Any

DEEP_TRIGGERS = [
    "40+ source files",
    "frontend/src/store",
    "frontend/src/entities",
    "frontend/src/systems",
    "frontend/src/components",
    "frontend/src/screens",
    "10 entities",
    "15 systems",
]


def is_deep_game_request(text: str) -> bool:
    lower = text.lower()
    return any(token in lower for token in DEEP_TRIGGERS) or ("required architecture" in lower and "systems" in lower and "entities" in lower)


def deep_game_blueprint(goal: str) -> dict[str, Any]:
    return {
        "app_name": "Space Colony Director" if "space" in goal.lower() or "colony" in goal.lower() else "DeepGame",
        "goal": goal,
        "kind": "deep-browser-game",
        "runtime": "react-vite-canvas",
        "needs_backend": False,
        "pages": [{"name": n, "purpose": n.lower()} for n in ["Command", "Colony", "Research", "Missions", "Stats", "Settings"]],
        "entities": [{"name": n} for n in ["Planet", "Tile", "Building", "Colonist", "Resource", "Job", "ResearchNode", "Mission", "Event", "Achievement"]],
        "systems": [{"name": n} for n in ["PlanetGeneration", "BuildingPlacement", "ConstructionQueue", "ResourceExtraction", "Energy", "Oxygen", "Food", "Colonist", "Jobs", "Research", "TechnologyUnlock", "Trade", "Events", "Missions", "Achievements", "Notifications", "Statistics", "SaveLoad"]],
        "app_plan": {
            "product_positioning": "A playable browser management simulation with a canvas colony map, real state, resource loops, research, missions, events, and working UI panels.",
            "primary_user_flows": ["Generate planet", "Place buildings", "Assign jobs", "Manage resources", "Unlock research", "Complete missions", "Save and load"],
            "navigation": ["Command", "Colony", "Research", "Missions", "Stats", "Settings"],
            "dashboard_widgets": ["Resource Bar", "Colonist Status", "Power/Oxygen/Food", "Construction Queue", "Research Progress", "Event Feed", "Mission Tracker"],
            "data_model": [
                {"name": "Planet", "fields": ["seed", "tiles", "day", "hazards"]},
                {"name": "Building", "fields": ["id", "type", "x", "y", "status", "workers", "output"]},
                {"name": "Colonist", "fields": ["id", "name", "job", "health", "morale", "home"]},
                {"name": "Resource", "fields": ["id", "name", "amount", "capacity", "delta"]},
            ],
            "seed_data_requirements": "Use a starter planet, resources, buildings, colonists, missions, events, and research nodes.",
            "design_system": {"tone": "sci-fi command center", "layout": "canvas map with top resource bar, side panels, bottom event tray", "visuals": ["neon panels", "tile map", "badges", "meters", "alerts"]},
            "acceptance_criteria": ["Preview opens", "User can place buildings", "Resources update live", "Save/load works", "No blank screen", "No fake buttons"],
        },
        "frontend_files": [],
        "backend_files": [],
        "dependency_topology": {},
        "notes": ["deep game blueprint forced by prompt architecture requirements"],
    }


def deep_game_paths() -> list[tuple[str, str, list[str], list[str]]]:
    base = [
        ("frontend/package.json", "frontend package", [], []),
        ("frontend/index.html", "html entry", [], []),
        ("README.md", "game instructions", [], []),
        ("frontend/src/main.jsx", "react entry", ["frontend/src/App.jsx", "frontend/src/styles.css"], []),
        ("frontend/src/App.jsx", "root app", ["frontend/src/screens/CommandScreen.jsx"], ["App"]),
        ("frontend/src/styles.css", "complete sci-fi responsive design system", [], []),
        ("frontend/src/store/gameState.js", "central game state and reducer", ["frontend/src/systems/PlanetGenerationSystem.js"], ["createInitialState", "gameReducer"]),
        ("frontend/src/store/selectors.js", "derived metrics and selectors", [], ["selectResources", "selectColonyHealth", "selectUnlockedTech", "selectMissionProgress"]),
        ("frontend/src/game/constants.js", "canvas constants", [], ["CANVAS_WIDTH", "CANVAS_HEIGHT", "TILE_SIZE"]),
        ("frontend/src/game/camera.js", "pan and zoom camera", [], ["createCamera", "panCamera", "zoomCamera"]),
        ("frontend/src/game/input.js", "pointer and keyboard input", [], ["createInputController"]),
        ("frontend/src/game/renderer.js", "canvas renderer", ["frontend/src/game/constants.js"], ["renderWorld"]),
        ("frontend/src/game/useGameLoop.js", "simulation loop hook", [], ["useGameLoop"]),
    ]
    data = ["resourceTypes", "buildingTypes", "jobTypes", "researchTree", "missionTemplates", "eventTemplates", "achievements", "tutorialSteps"]
    entities = ["Planet", "Tile", "Building", "Colonist", "Resource", "Job", "ResearchNode", "Mission", "ColonyEvent", "Achievement"]
    systems = ["PlanetGeneration", "BuildingPlacement", "ConstructionQueue", "ResourceExtraction", "Energy", "Oxygen", "Food", "Colonist", "Jobs", "Research", "TechnologyUnlock", "Trade", "Events", "Missions", "Achievements", "Notifications", "Statistics", "SaveLoad"]
    components = ["ResourceBar", "Toolbar", "WorldCanvas", "InspectorPanel", "ConstructionQueuePanel", "ColonistPanel", "ResearchPanel", "MissionPanel", "EventFeed", "AchievementPanel", "StatsPanel", "SettingsPanel"]
    screens = ["CommandScreen", "ColonyScreen", "ResearchScreen", "MissionsScreen", "StatsScreen", "SettingsScreen"]
    out = list(base)
    for name in data:
        export_name = ''.join(part.capitalize() for part in name.split('_'))
        out.append((f"frontend/src/data/{name}.js", f"{name} data", [], [export_name]))
    for name in entities:
        out.append((f"frontend/src/entities/{name}.js", f"{name} entity", [], [f"create{name}"]))
    for name in systems:
        out.append((f"frontend/src/systems/{name}System.js", f"{name} simulation system", [], [f"run{name}System"]))
    for name in components:
        out.append((f"frontend/src/components/{name}.jsx", f"{name} UI component", [], [name]))
    for name in screens:
        imports = ["frontend/src/store/gameState.js", "frontend/src/game/useGameLoop.js", "frontend/src/components/WorldCanvas.jsx", "frontend/src/components/ResourceBar.jsx", "frontend/src/components/Toolbar.jsx"] if name == "CommandScreen" else []
        out.append((f"frontend/src/screens/{name}.jsx", f"{name} screen", imports, [name]))
    return out
