from __future__ import annotations

import re
from dataclasses import dataclass, asdict

FRONTEND_CODE_EXT = (".js", ".jsx", ".ts", ".tsx")
FRONTEND_STYLE_EXT = (".css",)

# Candidate paths for the "app shell" file, tried in order, across both the
# generic dashboard-template layout and other layouts (game/root-level/etc).
APP_SHELL_CANDIDATES = (
    "frontend/src/App.jsx",
    "frontend/src/App.tsx",
    "frontend/App.tsx",
    "frontend/App.jsx",
    "frontend/src/main.tsx",
    "frontend/src/main.jsx",
)

# Filename fragments (case-insensitive) that indicate a "main visual surface"
# file: a dashboard, a primary game/sim screen, or a canvas renderer. This is
# intentionally name-based rather than one exact path so it works for any
# project layout (components/, screens/, scenes/, routes/, src/game/, etc).
MAIN_SURFACE_NAME_HINTS = (
    "dashboard", "gamescreen", "game_screen", "mainscreen", "main_screen",
    "canvasmap", "canvas_map", "worldcanvas", "world_canvas", "gamecanvas",
    "game_canvas", "colonyscreen", "commandscreen", "homescreen", "appshell",
)

# Filename fragments that indicate generated/seeded sample or reference data,
# independent of which directory convention the project uses (data/, fixtures/,
# entities/, content/, etc).
DATA_NAME_HINTS = ("sampledata", "seeddata", "fixtures", "mockdata", "content", "catalog")


def _count_terms(text: str, terms: list[str]) -> int:
    low = text.lower()
    return sum(1 for term in terms if term.lower() in low)


def _is_frontend_code_path(path: str) -> bool:
    return path.startswith("frontend/") and path.endswith(FRONTEND_CODE_EXT)


def _is_frontend_style_path(path: str) -> bool:
    return path.startswith("frontend/") and path.endswith(FRONTEND_STYLE_EXT)


def _all_frontend_code(files: dict[str, str]) -> str:
    return "\n".join(content for path, content in files.items() if _is_frontend_code_path(path))


def _all_frontend_styles(files: dict[str, str]) -> str:
    return "\n".join(content for path, content in files.items() if _is_frontend_style_path(path))


def _find_app_shell(files: dict[str, str]) -> str:
    for candidate in APP_SHELL_CANDIDATES:
        if files.get(candidate, "").strip():
            return files[candidate]
    # Fall back to any file literally named App.* or main.* anywhere under frontend/.
    for path, content in files.items():
        if not _is_frontend_code_path(path):
            continue
        stem = path.rsplit("/", 1)[-1].lower()
        if stem.startswith("app.") or stem.startswith("main."):
            if content.strip():
                return content
    return ""


def _find_named_surface(files: dict[str, str], hints: tuple[str, ...]) -> str:
    """Find the largest frontend file whose filename matches one of the given
    case-insensitive hints. Works regardless of directory layout."""
    best_path = ""
    best_content = ""
    for path, content in files.items():
        if not _is_frontend_code_path(path):
            continue
        stem = path.rsplit("/", 1)[-1].lower()
        if any(hint in stem for hint in hints) and len(content) > len(best_content):
            best_path, best_content = path, content
    return best_content


def _find_sample_data(files: dict[str, str]) -> str:
    chunks: list[str] = []
    for path, content in files.items():
        if not path.startswith("frontend/"):
            continue
        stem = path.rsplit("/", 1)[-1].lower()
        path_low = path.lower()
        is_data_dir = "/data/" in path_low or "/fixtures/" in path_low or "/entities/" in path_low
        is_data_name = any(hint in stem for hint in DATA_NAME_HINTS)
        if (is_data_dir or is_data_name) and path.endswith(FRONTEND_CODE_EXT):
            chunks.append(content)
    return "\n".join(chunks)


@dataclass
class QualityScore:
    product_architecture: int
    ui_depth: int
    workflow_depth: int
    data_richness: int
    design_system: int
    total: int
    issues: list[str]
    suggestions: list[str]


def score_product_quality(files: dict[str, str]) -> QualityScore:
    issues: list[str] = []
    suggestions: list[str] = []

    app = _find_app_shell(files)
    main_surface = _find_named_surface(files, MAIN_SURFACE_NAME_HINTS)
    sample = _find_sample_data(files)
    styles = _all_frontend_styles(files)
    all_frontend = _all_frontend_code(files)

    # Vocabulary covers both business/SaaS-style apps and game/simulation apps,
    # since the pipeline generates both kinds of products.
    architecture_terms = [
        "persona", "workflow", "permission", "role", "audit", "automation", "notification",
        "report", "client", "team", "project", "pipeline",
        "system", "entity", "simulation", "economy", "inventory", "scene", "level", "state machine",
    ]
    ui_terms = [
        "dashboard", "activity", "search", "filter", "status", "timeline", "kanban", "chart",
        "table", "modal", "empty", "loading", "error", "quick action",
        "canvas", "hud", "toolbar", "minimap", "panel", "overlay", "inventory", "menu",
    ]
    workflow_terms = [
        "onclick", "usestate", "filter(", "map(", "set", "create", "update", "delete",
        "selected", "active", "tab", "search",
        "onpointerdown", "onmousedown", "dispatch", "reducer", "usereducer", "useeffect",
    ]
    data_terms = [
        "projects", "tasks", "users", "comments", "activities", "attachments", "status",
        "priority", "duedate", "owner", "team",
        "entities", "resources", "buildings", "vehicles", "tiles", "inventory", "items", "level",
    ]
    design_terms = [
        "linear-gradient", "grid", "flex", "box-shadow", "border-radius", "badge", "sidebar",
        "card", "responsive", "@media", "gap", "transition",
        "canvas", "hud", "toolbar", "animation", "keyframes",
    ]

    jsx_tag_count = len(re.findall(r"<[A-Za-z]", app + main_surface))

    product_architecture = min(100, _count_terms(all_frontend, architecture_terms) * 9)
    ui_depth = min(100, _count_terms(all_frontend, ui_terms) * 7 + min(jsx_tag_count, 60))
    workflow_depth = min(100, _count_terms(all_frontend, workflow_terms) * 8)
    data_richness = min(100, _count_terms(sample + all_frontend, data_terms) * 7 + min(len(sample) // 80, 35))
    design_system = min(100, _count_terms(styles, design_terms) * 8 + min(len(styles) // 120, 25))

    # "Main surface" depth check stands in for the old hardcoded Dashboard.jsx
    # check, but applies to whatever file actually serves that role in this
    # project (dashboard, game screen, canvas renderer, etc).
    if main_surface:
        if len(main_surface.strip()) < 1200:
            issues.append("Main UI surface (dashboard/screen/canvas) is too shallow")
            suggestions.append("Flesh out the primary screen with real state-driven sections: status/metrics, lists, and interactive controls.")
            ui_depth = min(ui_depth, 55)
    elif not app or len(app.strip()) < 1200:
        # No dedicated dashboard/screen file AND the app shell itself is thin.
        issues.append("No substantial main UI surface found")
        suggestions.append("Add a real primary screen (dashboard, game screen, or canvas view) with meaningful content, not just a thin app shell.")
        ui_depth = min(ui_depth, 55)

    if sample:
        if len(sample.strip()) < 2000:
            issues.append("Sample/seed data is too thin")
            suggestions.append("Generate realistic connected records (entities, resources, tasks, etc.) rather than a handful of placeholder rows.")
            data_richness = min(data_richness, 55)
    elif _count_terms(all_frontend, data_terms) < 4:
        issues.append("Sample/seed data is too thin")
        suggestions.append("Generate realistic connected sample/seed data backing the main screens.")
        data_richness = min(data_richness, 55)

    if styles.strip() and len(styles.strip()) < 1500:
        issues.append("Design system is too basic")
        suggestions.append("Add a richer responsive design system: cards, badges, sidebars/panels, grids, and interaction states.")
        design_system = min(design_system, 55)
    elif not styles.strip():
        issues.append("No styling found")
        suggestions.append("Add CSS for the app shell and its main screens.")
        design_system = min(design_system, 30)

    if _count_terms(all_frontend, ["empty", "loading", "error"]) < 1:
        issues.append("Missing product states")
        suggestions.append("Add empty, loading, and/or error states to key screens.")
        ui_depth = min(ui_depth, 65)

    total = round((product_architecture + ui_depth + workflow_depth + data_richness + design_system) / 5)
    return QualityScore(product_architecture, ui_depth, workflow_depth, data_richness, design_system, total, issues, suggestions)


def quality_as_dict(score: QualityScore) -> dict:
    return asdict(score)


def quality_repair_prompt(score: QualityScore) -> str:
    if not score.issues:
        return "Product quality passed. Preserve quality while repairing build issues."
    return (
        "Product quality failed. Improve the app as a real product, not a scaffold.\n"
        f"Scores: architecture={score.product_architecture}, ui={score.ui_depth}, workflow={score.workflow_depth}, data={score.data_richness}, design={score.design_system}, total={score.total}.\n"
        "Issues:\n- " + "\n- ".join(score.issues) + "\n"
        "Required improvements:\n- " + "\n- ".join(score.suggestions)
    )
