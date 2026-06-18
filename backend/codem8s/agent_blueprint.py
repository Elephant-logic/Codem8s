from __future__ import annotations
import json, re
from typing import Any
from .models import ProjectSpec
from .agent_llm import chat_json

def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "generated-app"

def title_from_idea(idea: str) -> str:
    return " ".join(part.capitalize() for part in slug(idea).split("-")[:4]) or "Generated App"

def fallback_blueprint(idea: str) -> dict[str, Any]:
    text = idea.lower()
    if any(w in text for w in ["game", "snake", "platform", "arcade", "canvas", "puzzle"]):
        return {
            "app_name": title_from_idea(idea), "goal": idea, "kind": "game",
            "runtime": "react", "needs_backend": False,
            "pages": [{"name": "Game", "purpose": "play"}, {"name": "Start", "purpose": "start"}, {"name": "Scoreboard", "purpose": "score"}],
            "entities": [], "notes": ["fallback game blueprint"],
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
        "app_name": title_from_idea(idea), "goal": idea, "kind": "business_app",
        "runtime": "react-fastapi-sqlite", "needs_backend": True,
        "pages": [{"name": p, "purpose": p.lower()} for p in pages],
        "entities": entities, "notes": ["fallback business blueprint"],
    }

def plan_with_api(idea: str) -> dict[str, Any] | None:
    system = "You are Codem8s Planner. Return JSON only. Think first. Do not default to CRUD. Plan pages, entities, workflows, files. If game, plan game loop, controls, scenes. Required keys: app_name, goal, kind, runtime, needs_backend, pages, entities, frontend_files, backend_files, notes."
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

def files_for_blueprint(bp: dict[str, Any]) -> dict[str, str]:
    files = {
        "frontend/package.json": "frontend package", "frontend/index.html": "html entry",
        "frontend/src/main.jsx": "react entry", "frontend/src/App.jsx": "app shell",
        "frontend/src/styles.css": "styles", "README.md": "instructions",
    }
    if bp.get("kind") == "game" or bp.get("needs_backend") is False:
        files.update({
            "frontend/src/game/GameCanvas.jsx": "game canvas",
            "frontend/src/game/useGameLoop.js": "game loop",
            "frontend/src/game/input.js": "input",
            "frontend/src/game/collision.js": "collision",
        })
        return files
    files.update({
        "backend/main.py": "multi entity API", "backend/store.py": "sqlite storage",
        "backend/requirements.txt": "backend requirements",
        "frontend/src/components/Nav.jsx": "navigation",
        "frontend/src/components/Dashboard.jsx": "dashboard",
        "frontend/src/components/EntityPage.jsx": "entity page",
        "frontend/src/components/FormBuilder.jsx": "form builder",
    })
    return files

def build_spec(idea: str, stack: str = "react-fastapi") -> ProjectSpec:
    bp = blueprint_from_idea(idea, use_api=True)
    return ProjectSpec(
        app_name=bp["app_name"], goal=idea, stack=bp.get("runtime", stack),
        features=["agent planned blueprint", f"kind: {bp.get('kind')}", "api planned once", "files generated from saved blueprint"],
        files=files_for_blueprint(bp), change_log=["BLUEPRINT_JSON:" + json.dumps(bp)]
    )

def apply_instruction(spec: ProjectSpec, instruction: str) -> ProjectSpec:
    bp = blueprint_from_idea(spec.goal + "\nChange request: " + instruction, use_api=True)
    spec.features = ["agent replanned blueprint", f"kind: {bp.get('kind')}", "api planned once", "files generated from saved blueprint"]
    spec.files = files_for_blueprint(bp)
    spec.change_log.append("INSTRUCTION:" + instruction)
    spec.change_log.append("BLUEPRINT_JSON:" + json.dumps(bp))
    return spec
