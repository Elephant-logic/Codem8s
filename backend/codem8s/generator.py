from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .models import ProjectSpec
from .settings import get_openai_key, get_openai_model

BASE_FILES: Dict[str, str] = {
    "backend/main.py": "FastAPI app exposing project, change, validate, export endpoints",
    "backend/generator.py": "spec builder and file generator",
    "backend/validator.py": "strict file and project validator",
    "backend/runner.py": "syntax and smoke-test runner",
    "backend/settings.py": "local settings and stored API key management",
    "backend/exporter.py": "zip export utility",
    "frontend/package.json": "React package config",
    "frontend/src/App.jsx": "live steering user interface",
    "frontend/src/main.jsx": "React entry point",
    "frontend/src/styles.css": "application styling",
    "README.md": "setup and usage instructions",
}

FEATURE_HINTS = {
    "login": "authentication screens and protected routes",
    "dashboard": "dashboard cards, charts, and saved runs",
    "game": "interactive canvas or game loop",
    "api": "REST API endpoints and typed schemas",
    "database": "SQLite persistence layer",
    "upload": "file upload and inspection workflow",
    "export": "zip export and project download",
    "chat": "streaming chat panel and message history",
}

CORE_COPY_FILES = {
    "backend/generator.py": "generator.py",
    "backend/validator.py": "validator.py",
    "backend/settings.py": "settings.py",
    "backend/runner.py": "runner.py",
    "backend/exporter.py": "exporter.py",
}

REQUIRED_NAMES = {
    "backend/main.py": ["app"],
    "backend/generator.py": ["build_spec", "generate_file"],
    "backend/validator.py": ["validate_file", "detect_placeholders"],
    "backend/settings.py": ["load_settings", "save_settings", "settings_status"],
}


def infer_features(idea: str) -> List[str]:
    text = idea.lower()
    features = ["locked project spec", "file-by-file build", "live change instructions", "strict validation", "zip export"]
    for key, value in FEATURE_HINTS.items():
        if key in text:
            features.append(value)
    return list(dict.fromkeys(features))


def build_spec(idea: str, stack: str = "react-fastapi") -> ProjectSpec:
    clean = " ".join(idea.strip().split())
    name = "Codem8s Project" if len(clean) < 40 else clean[:40].rstrip()
    if "codem8" in clean.lower():
        name = "Codem8s"
    return ProjectSpec(app_name=name, goal=clean, stack=stack, features=infer_features(clean), files=BASE_FILES.copy())


def apply_instruction(spec: ProjectSpec, instruction: str) -> ProjectSpec:
    text = " ".join(instruction.strip().split())
    if text:
        spec.change_log.append(text)
    lowered = text.lower()
    if any(word in lowered for word in ["login", "auth", "user account"]):
        spec.features.append("authentication flow")
        spec.files["frontend/src/auth.jsx"] = "authentication panel"
        spec.files["backend/auth.py"] = "token issuing and verification helpers"
    if any(word in lowered for word in ["sqlite", "database", "save history"]):
        spec.features.append("SQLite project history")
        spec.files["backend/store.py"] = "SQLite storage for projects and generated files"
    if any(word in lowered for word in ["test", "pytest"]):
        spec.features.append("test suite")
        spec.files["backend/tests/test_validator.py"] = "validator unit tests"
    spec.features = list(dict.fromkeys(spec.features))
    return spec


def _extract_code_block(text: str) -> str:
    marker = "```"
    if marker not in text:
        return text.strip()
    parts = text.split(marker)
    for part in parts:
        cleaned = part.strip()
        if cleaned.startswith(("python", "javascript", "jsx", "json", "css", "html", "bash", "markdown")):
            first_newline = cleaned.find("\n")
            return cleaned[first_newline + 1:].strip() if first_newline >= 0 else ""
    return parts[1].strip()


def _core_file(path: str) -> Optional[str]:
    local_name = CORE_COPY_FILES.get(path)
    if local_name:
        return Path(__file__).with_name(local_name).read_text(encoding="utf-8")
    return None


def _static_file(path: str, spec: ProjectSpec) -> Optional[str]:
    if path == "README.md":
        return f"""# {spec.app_name}\n\n{spec.goal}\n\n## Stack\n\n{spec.stack}\n\n## How to use\n\nCreate a spec, build files, steer with extra instructions, validate, then export the zip.\n"""
    if path == "frontend/package.json":
        return '{"scripts":{"dev":"vite --host 0.0.0.0","build":"vite build","preview":"vite preview"},"dependencies":{"@vitejs/plugin-react":"latest","vite":"latest","react":"latest","react-dom":"latest","lucide-react":"latest"},"devDependencies":{}}'
    if path == "frontend/src/main.jsx":
        return "import React from 'react';\nimport { createRoot } from 'react-dom/client';\nimport App from './App.jsx';\nimport './styles.css';\n\ncreateRoot(document.getElementById('root')).render(<App />);\n"
    if path == "frontend/src/styles.css":
        return "body{margin:0;background:#0b1020;color:#e8ecff;font-family:Inter,system-ui,Arial}.app{padding:24px;max-width:1200px;margin:auto}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.card{background:#151b33;border:1px solid #2a335a;border-radius:16px;padding:16px;margin:16px 0}textarea,input{background:#090d1a;color:#fff;border:1px solid #33406e;border-radius:10px;padding:10px;box-sizing:border-box}textarea{width:100%;min-height:120px}button{background:#6d7cff;color:white;border:0;border-radius:10px;padding:10px 14px;margin:4px;cursor:pointer}.log{white-space:pre-wrap;font-family:ui-monospace,monospace;font-size:13px}.file{padding:6px;border-bottom:1px solid #273052}.bad{color:#ff9f9f}.ok{color:#93f5b5}"
    return None


def ai_generate_file(path: str, spec: ProjectSpec, previous_errors: Optional[List[str]] = None) -> Optional[str]:
    api_key = get_openai_key()
    if not api_key:
        return None
    required = REQUIRED_NAMES.get(path, [])
    error_text = "\n".join(previous_errors or [])
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        prompt = f"""
You are Codem8s, a strict full-stack code builder.
Write one complete file only.

Locked app spec:
app_name: {spec.app_name}
goal: {spec.goal}
stack: {spec.stack}
features: {spec.features}
manifest: {spec.files}

Target file: {path}
Purpose: {spec.files.get(path, 'project file')}
Names that must exist in this file: {required}
Earlier validation errors to fix: {error_text or 'none'}

Rules:
- Return only the file content in one code block.
- No empty shell functions.
- No fake behaviour.
- Python must parse.
- Match the target file and the locked manifest.
""".strip()
        response = client.chat.completions.create(
            model=get_openai_model(),
            messages=[
                {"role": "system", "content": "You write complete runnable files that satisfy exact validation rules."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=4000,
        )
        return _extract_code_block(response.choices[0].message.content or "")
    except Exception as exc:
        return f"# AI generation error for {path}\nERROR = {exc!r}\n"


def generate_file(path: str, spec: ProjectSpec, use_ai: bool = True, previous_errors: Optional[List[str]] = None) -> str:
    core = _core_file(path)
    if core is not None:
        return core
    static = _static_file(path, spec)
    if static is not None:
        return static
    if use_ai:
        generated = ai_generate_file(path, spec, previous_errors)
        if generated:
            return generated
    purpose = spec.files.get(path, "project file")
    return f"# Generated file for {path}\nPURPOSE = {purpose!r}\n"