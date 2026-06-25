from __future__ import annotations

import re
from typing import Any

# Structural detection: look for the *shape* of a "deep architecture" request
# (numeric minimums on files/entities/systems) rather than exact phrases from
# any one historical prompt. This generalizes across rewordings like
# "at least 40 frontend files" / "40+ source files" / "minimum of 40 files".
FILES_PATTERN = re.compile(r"(\d+)\+?\s*(?:frontend |source |project )?files", re.I)
ENTITIES_PATTERN = re.compile(r"(\d+)\+?\s*(?:domain |game )?entit(?:y|ies)", re.I)
SYSTEMS_PATTERN = re.compile(r"(\d+)\+?\s*(?:simulation |game |core )?systems", re.I)

# Kept for backward compatibility with prompts that happen to use this exact
# phrasing, but no longer the only way in.
LEGACY_PHRASES = [
    "40+ source files",
    "frontend/src/store",
    "frontend/src/entities",
    "frontend/src/systems",
]

FILES_THRESHOLD = 25
ENTITIES_THRESHOLD = 8
SYSTEMS_THRESHOLD = 10


def _max_match(pattern: re.Pattern, text: str) -> int:
    values = [int(match) for match in pattern.findall(text)]
    return max(values) if values else 0


def is_deep_game_request(text: str) -> bool:
    lower = text.lower()
    if any(token in lower for token in LEGACY_PHRASES):
        return True
    files_n = _max_match(FILES_PATTERN, lower)
    entities_n = _max_match(ENTITIES_PATTERN, lower)
    systems_n = _max_match(SYSTEMS_PATTERN, lower)
    hits = sum([
        files_n >= FILES_THRESHOLD,
        entities_n >= ENTITIES_THRESHOLD,
        systems_n >= SYSTEMS_THRESHOLD,
    ])
    # Require at least two of the three numeric signals so a casual mention of
    # "a few files" or "one entity" doesn't accidentally trip this path.
    return hits >= 2


# Domain packs: keyword -> (app_name, entities, systems, pages, tone, visuals).
# Each pack supplies real, domain-specific nouns instead of one fixed cast, so
# a transport-tycoon request gets vehicles/roads/cargo and a colony-sim
# request gets planets/colonists, etc. New genres can be added here without
# touching the matching/rendering logic.
DOMAIN_PACKS: list[dict[str, Any]] = [
    {
        "keywords": ["transport", "tycoon", "railway", "rail", "logistics", "cargo", "shipping", "freight", "traffic"],
        "app_name": "Transport Tycoon",
        "entities": ["Town", "Vehicle", "Road", "Railway", "Station", "Airport", "Port", "Ship",
                     "CargoType", "Route", "Company", "Industry"],
        "systems": ["ProceduralTerrain", "Pathfinding", "VehicleMovement", "CargoGeneration",
                    "SupplyAndDemand", "TownGrowth", "Economy", "TimeProgression", "RouteScheduling",
                    "Construction", "Maintenance", "Events", "Notifications", "Achievements",
                    "Statistics", "Minimap", "ZoomAndPan", "SaveLoad"],
        "pages": ["Map", "Company", "Finance", "Routes", "Vehicles", "Settings"],
        "tone": "industrial transport management sim",
        "visuals": ["canvas world map", "minimap", "route overlays", "vehicle icons", "HUD toolbars"],
    },
    {
        "keywords": ["city builder", "city-builder", "citybuilder", "sim city", "simcity", "urban planning"],
        "app_name": "City Builder",
        "entities": ["City", "Zone", "Building", "Citizen", "Service", "Road", "Utility", "Budget", "PolicyEvent", "District"],
        "systems": ["ProceduralTerrain", "ZoningSimulation", "CitizenGrowth", "TrafficFlow", "Utilities",
                    "Budget", "TaxPolicy", "ServiceCoverage", "Pollution", "Happiness", "Events",
                    "Notifications", "Achievements", "Statistics", "Minimap", "ZoomAndPan", "SaveLoad"],
        "pages": ["City", "Budget", "Policies", "Statistics", "Settings"],
        "tone": "urban planning management sim",
        "visuals": ["canvas city map", "minimap", "zone overlays", "building icons", "HUD panels"],
    },
    {
        "keywords": ["farm", "farming", "harvest", "crop", "agriculture"],
        "app_name": "Farm Sim",
        "entities": ["Field", "Crop", "Animal", "Building", "Market", "Season", "Worker", "Tool", "Order", "Storage"],
        "systems": ["ProceduralTerrain", "PlantingAndGrowth", "Harvesting", "AnimalCare", "Weather",
                    "Season", "Market", "SupplyAndDemand", "Economy", "Events", "Notifications",
                    "Achievements", "Statistics", "Minimap", "ZoomAndPan", "SaveLoad"],
        "pages": ["Farm", "Market", "Storage", "Stats", "Settings"],
        "tone": "cozy farming management sim",
        "visuals": ["canvas farm map", "minimap", "crop overlays", "weather indicator", "HUD panels"],
    },
    {
        "keywords": ["space", "colony", "planet", "interstellar", "mars", "exoplanet"],
        "app_name": "Space Colony Director",
        "entities": ["Planet", "Tile", "Building", "Colonist", "Resource", "Job", "ResearchNode", "Mission", "Event", "Achievement"],
        "systems": ["PlanetGeneration", "BuildingPlacement", "ConstructionQueue", "ResourceExtraction",
                    "Energy", "Oxygen", "Food", "Colonist", "Jobs", "Research", "TechnologyUnlock",
                    "Trade", "Events", "Missions", "Achievements", "Notifications", "Statistics", "SaveLoad"],
        "pages": ["Command", "Colony", "Research", "Missions", "Stats", "Settings"],
        "tone": "sci-fi command center",
        "visuals": ["neon panels", "tile map", "badges", "meters", "alerts"],
    },
]

GENERIC_PACK: dict[str, Any] = {
    "app_name": "Deep Sim",
    "entities": ["Actor", "Location", "Resource", "Item", "Job", "Event", "Mission", "Achievement", "Faction", "Inventory"],
    "systems": ["WorldGeneration", "Movement", "Pathfinding", "ResourceGeneration", "SupplyAndDemand",
                "Growth", "Economy", "TimeProgression", "Events", "Missions", "Achievements",
                "Notifications", "Statistics", "Minimap", "ZoomAndPan", "SaveLoad"],
    "pages": ["Main", "Inventory", "Map", "Stats", "Settings"],
    "tone": "management simulation",
    "visuals": ["canvas world view", "minimap", "HUD panels", "badges", "meters"],
}


def _select_domain_pack(goal: str) -> dict[str, Any]:
    lower = goal.lower()
    for pack in DOMAIN_PACKS:
        if any(keyword in lower for keyword in pack["keywords"]):
            return pack
    return GENERIC_PACK


def deep_game_blueprint(goal: str) -> dict[str, Any]:
    pack = _select_domain_pack(goal)
    entities = pack["entities"]
    systems = pack["systems"]
    pages = pack["pages"]
    return {
        "app_name": pack["app_name"],
        "goal": goal,
        "kind": "deep-browser-game",
        "runtime": "react-vite-canvas",
        "needs_backend": False,
        "pages": [{"name": n, "purpose": n.lower()} for n in pages],
        "entities": [{"name": n} for n in entities],
        "systems": [{"name": n} for n in systems],
        "app_plan": {
            "product_positioning": f"A playable browser {pack['tone']} with a canvas world map, real state, simulation loops, and working UI panels.",
            "primary_user_flows": ["Generate world", "Place/build core structures", "Manage resources",
                                    "Progress over time", "Complete missions/events", "Save and load"],
            "navigation": pages,
            "dashboard_widgets": ["Resource Bar", "Status Panel", "Build/Construction Queue", "Progress Tracker", "Event Feed"],
            "data_model": [{"name": name, "fields": ["id", "name", "status"]} for name in entities[:4]],
            "seed_data_requirements": f"Use realistic starter {entities[0].lower()}s, {entities[1].lower() if len(entities) > 1 else 'resources'}, and a populated world, not placeholder records.",
            "design_system": {"tone": pack["tone"], "layout": "canvas world view with HUD panels", "visuals": pack["visuals"]},
            "acceptance_criteria": ["Preview opens", "User can interact with the world", "State updates live",
                                     "Save/load works", "No blank screen", "No fake buttons"],
        },
        "frontend_files": [],
        "backend_files": [],
        "dependency_topology": {},
        "notes": [f"deep game blueprint selected domain pack: {pack['app_name']}"],
    }


def deep_game_paths(goal: str = "") -> list[tuple[str, str, list[str], list[str]]]:
    pack = _select_domain_pack(goal)
    entities = pack["entities"]
    systems = pack["systems"]
    screens = [f"{name.replace(' ', '')}Screen" for name in pack["pages"]]
    main_screen = screens[0] if screens else "MainScreen"

    base = [
        ("frontend/package.json", "frontend package", [], []),
        ("frontend/index.html", "html entry", [], []),
        ("README.md", "game instructions", [], []),
        ("frontend/src/main.jsx", "react entry", ["frontend/src/App.jsx", "frontend/src/styles.css"], []),
        ("frontend/src/App.jsx", "root app", [f"frontend/src/screens/{main_screen}.jsx"], ["App"]),
        ("frontend/src/styles.css", "complete responsive design system", [], []),
        ("frontend/src/store/gameState.js", "central game state and reducer",
         ["frontend/src/systems/" + systems[0] + "System.js"], ["createInitialState", "gameReducer"]),
        ("frontend/src/store/selectors.js", "derived metrics and selectors", [],
         ["selectResources", "selectProgress", "selectStatus"]),
        ("frontend/src/game/constants.js", "canvas constants", [], ["CANVAS_WIDTH", "CANVAS_HEIGHT", "TILE_SIZE"]),
        ("frontend/src/game/camera.js", "pan and zoom camera", [], ["createCamera", "panCamera", "zoomCamera"]),
        ("frontend/src/game/input.js", "pointer and keyboard input", [], ["createInputController"]),
        ("frontend/src/game/renderer.js", "canvas renderer", ["frontend/src/game/constants.js"], ["renderWorld"]),
        ("frontend/src/game/useGameLoop.js", "simulation loop hook", [], ["useGameLoop"]),
    ]
    data = ["catalog", "startConfig", "missionTemplates", "eventTemplates", "achievements", "tutorialSteps"]
    components = ["ResourceBar", "Toolbar", "WorldCanvas", "InspectorPanel", "QueuePanel",
                  "StatusPanel", "EventFeed", "AchievementPanel", "StatsPanel", "SettingsPanel"]
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
    for screen in screens:
        imports = ["frontend/src/store/gameState.js", "frontend/src/game/useGameLoop.js",
                   "frontend/src/components/WorldCanvas.jsx", "frontend/src/components/ResourceBar.jsx",
                   "frontend/src/components/Toolbar.jsx"] if screen == main_screen else []
        out.append((f"frontend/src/screens/{screen}.jsx", f"{screen} screen", imports, [screen]))
    return out
