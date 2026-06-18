from __future__ import annotations

import re
from typing import Dict, List

from .models import ProjectSpec


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:36] or "generated-app"


def app_kind(idea: str) -> str:
    text = idea.lower()
    options = [
        ("job", ["job", "career", "interview", "employer"]),
        ("crm", ["crm", "customer", "client", "contact", "lead", "sales"]),
        ("inventory", ["inventory", "stock", "product", "sku", "warehouse"]),
        ("booking", ["booking", "appointment", "reservation", "schedule", "calendar"]),
        ("todo", ["todo", "task", "kanban"]),
        ("notes", ["note", "journal", "wiki"]),
        ("expense", ["expense", "budget", "invoice", "payment", "finance"]),
    ]
    for kind, words in options:
        if any(word in text for word in words):
            return kind
    return "records"


FIELD_LIBRARY = {
    "job": [
        {"name": "company", "label": "Company", "type": "text", "required": True},
        {"name": "role", "label": "Role", "type": "text", "required": True},
        {"name": "status", "label": "Status", "type": "select", "default": "saved", "options": ["saved", "applied", "interview", "offer", "rejected"]},
        {"name": "notes", "label": "Notes", "type": "textarea", "default": ""},
        {"name": "next_action", "label": "Next action", "type": "text", "default": ""},
    ],
    "crm": [
        {"name": "name", "label": "Lead name", "type": "text", "required": True},
        {"name": "company", "label": "Company", "type": "text", "default": ""},
        {"name": "email", "label": "Email", "type": "email", "default": ""},
        {"name": "status", "label": "Pipeline stage", "type": "select", "default": "lead", "options": ["lead", "contacted", "proposal", "won", "lost"]},
        {"name": "notes", "label": "Notes", "type": "textarea", "default": ""},
        {"name": "next_action", "label": "Next action", "type": "text", "default": ""},
    ],
    "inventory": [
        {"name": "product", "label": "Product", "type": "text", "required": True},
        {"name": "sku", "label": "SKU", "type": "text", "default": ""},
        {"name": "quantity", "label": "Quantity", "type": "number", "default": "0"},
        {"name": "status", "label": "Stock state", "type": "select", "default": "in_stock", "options": ["in_stock", "low", "ordered", "discontinued"]},
        {"name": "supplier", "label": "Supplier", "type": "text", "default": ""},
        {"name": "notes", "label": "Notes", "type": "textarea", "default": ""},
    ],
    "booking": [
        {"name": "customer", "label": "Customer", "type": "text", "required": True},
        {"name": "service", "label": "Service", "type": "text", "required": True},
        {"name": "date", "label": "Date", "type": "date", "default": ""},
        {"name": "status", "label": "Booking status", "type": "select", "default": "booked", "options": ["booked", "confirmed", "completed", "cancelled"]},
        {"name": "notes", "label": "Notes", "type": "textarea", "default": ""},
    ],
    "todo": [
        {"name": "task", "label": "Task", "type": "text", "required": True},
        {"name": "owner", "label": "Owner", "type": "text", "default": ""},
        {"name": "status", "label": "Status", "type": "select", "default": "todo", "options": ["todo", "doing", "done", "blocked"]},
        {"name": "priority", "label": "Priority", "type": "select", "default": "medium", "options": ["low", "medium", "high"]},
        {"name": "notes", "label": "Notes", "type": "textarea", "default": ""},
    ],
    "notes": [
        {"name": "title", "label": "Title", "type": "text", "required": True},
        {"name": "category", "label": "Category", "type": "text", "default": ""},
        {"name": "status", "label": "Status", "type": "select", "default": "draft", "options": ["draft", "active", "archived"]},
        {"name": "notes", "label": "Notes", "type": "textarea", "default": ""},
    ],
    "expense": [
        {"name": "title", "label": "Title", "type": "text", "required": True},
        {"name": "amount", "label": "Amount", "type": "number", "default": "0"},
        {"name": "category", "label": "Category", "type": "text", "default": ""},
        {"name": "status", "label": "Status", "type": "select", "default": "pending", "options": ["pending", "paid", "overdue"]},
        {"name": "notes", "label": "Notes", "type": "textarea", "default": ""},
    ],
    "records": [
        {"name": "title", "label": "Title", "type": "text", "required": True},
        {"name": "description", "label": "Description", "type": "textarea", "default": ""},
        {"name": "status", "label": "Status", "type": "select", "default": "active", "options": ["active", "paused", "done"]},
        {"name": "notes", "label": "Notes", "type": "textarea", "default": ""},
    ],
}

WORKFLOW_LIBRARY = {
    "crm": ["Leads", "Pipeline", "Companies", "Tasks"],
    "inventory": ["Products", "Stock", "Suppliers", "Movements"],
    "booking": ["Appointments", "Customers", "Services", "Calendar"],
    "job": ["Jobs", "Interviews", "Companies", "FollowUps"],
    "todo": ["Board", "Tasks", "Priorities"],
    "notes": ["Notes", "Categories", "Archive"],
    "expense": ["Expenses", "Categories", "Payments"],
    "records": ["Records", "Dashboard"],
}


def fields_for(idea: str) -> List[dict]:
    return FIELD_LIBRARY[app_kind(idea)]


def workflows_for(idea: str) -> List[str]:
    return WORKFLOW_LIBRARY.get(app_kind(idea), WORKFLOW_LIBRARY["records"])


def wants_sqlite(idea: str) -> bool:
    text = idea.lower()
    return any(word in text for word in ["sqlite", "database", "save", "persist", "crm", "note", "job", "inventory", "booking", "todo"])


def infer_features(idea: str) -> List[str]:
    kind = app_kind(idea)
    features = ["React frontend", "FastAPI backend", f"{kind} workflow", "dynamic form", "dynamic list", "workflow pages", "navigation"]
    if "dashboard" in idea.lower() or kind in {"job", "crm", "inventory", "expense"}:
        features.append("dashboard summary")
    if wants_sqlite(idea):
        features.append("SQLite persistence")
    if "login" in idea.lower() or "account" in idea.lower() or "user" in idea.lower():
        features.append("local profile panel")
    return list(dict.fromkeys(features))


def infer_files(idea: str, stack: str = "react-fastapi") -> Dict[str, str]:
    kind = app_kind(idea)
    files = {
        "backend/main.py": f"FastAPI backend for {kind}",
        "backend/requirements.txt": "backend dependencies",
        "frontend/package.json": "frontend dependencies",
        "frontend/index.html": "HTML entry",
        "frontend/src/App.jsx": "main React app shell",
        "frontend/src/main.jsx": "React entry",
        "frontend/src/styles.css": "styles",
        "frontend/src/components/DynamicForm.jsx": "generated form component",
        "frontend/src/components/RecordList.jsx": "generated list component",
        "frontend/src/components/WorkflowTabs.jsx": "workflow navigation tabs",
        "frontend/src/components/WorkflowPage.jsx": "app-specific workflow page",
        "README.md": "instructions",
    }
    if wants_sqlite(idea):
        files["backend/store.py"] = "SQLite helper used by backend"
    if "dashboard" in idea.lower() or kind in {"job", "crm", "inventory", "expense"}:
        files["frontend/src/components/Dashboard.jsx"] = "dashboard component"
    if "login" in idea.lower() or "account" in idea.lower() or "user" in idea.lower():
        files["frontend/src/components/ProfilePanel.jsx"] = "local profile panel"
    return files


def build_spec(idea: str, stack: str = "react-fastapi") -> ProjectSpec:
    clean = " ".join(idea.strip().split())
    name = " ".join(part.capitalize() for part in slug(clean).split("-")[:4])
    return ProjectSpec(app_name=name or "Generated App", goal=clean, stack=stack, features=infer_features(clean), files=infer_files(clean, stack))


def apply_instruction(spec: ProjectSpec, instruction: str) -> ProjectSpec:
    text = " ".join(instruction.strip().split())
    if text:
        spec.change_log.append(text)
    spec.features = list(dict.fromkeys(spec.features + infer_features(text)))
    for path, purpose in infer_files(spec.goal + " " + text, spec.stack).items():
        spec.files.setdefault(path, purpose)
    return spec
