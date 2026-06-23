from __future__ import annotations

import json
from typing import Optional

from .models import ProjectSpec
from .agent_blueprint import build_spec, apply_instruction
from .factory_renderer import render_file
from .agent_builder import build_file_with_api, is_weak_code

API_FIRST_EXTENSIONS = (".jsx", ".js", ".tsx", ".ts", ".css", ".py")
CODE_EXTENSIONS = (".jsx", ".js", ".tsx", ".ts", ".css", ".py")


def should_use_api_builder(path: str, use_ai: bool) -> bool:
    if not use_ai:
        return False
    if path in {
        "frontend/package.json",
        "frontend/index.html",
        "frontend/src/main.jsx",
        "frontend/src/main.tsx",
        "backend/requirements.txt",
        "README.md",
    }:
        return False
    return path.endswith(API_FIRST_EXTENSIONS)


def _spec_uses_tsx(spec: ProjectSpec) -> bool:
    return any(path.endswith((".ts", ".tsx")) for path in spec.files)


def _spec_uses_router(spec: ProjectSpec) -> bool:
    text = (spec.goal + "\n" + json.dumps(spec.files)).lower()
    return "route" in text or "router" in text or "frontend/src/routes" in text or "frontend/routes" in text


def fallback_file(path: str, spec: ProjectSpec) -> str:
    rendered = render_file(path, spec)
    if rendered is not None:
        return rendered

    if path == "backend/requirements.txt":
        return "fastapi==0.111.0\nuvicorn[standard]==0.30.1\npydantic==2.7.4\npython-dotenv==1.0.1\n"

    if path == "frontend/package.json":
        deps = {"@vitejs/plugin-react": "latest", "vite": "latest", "react": "latest", "react-dom": "latest"}
        dev_deps = {}
        if _spec_uses_tsx(spec):
            deps.update({"typescript": "latest", "@types/react": "latest", "@types/react-dom": "latest"})
        if _spec_uses_router(spec):
            deps["react-router-dom"] = "latest"
        return json.dumps({"scripts": {"dev": "vite --host 0.0.0.0", "build": "vite build", "preview": "vite preview"}, "dependencies": deps, "devDependencies": dev_deps}, separators=(",", ":"))

    if path == "frontend/index.html":
        if "frontend/src/main.tsx" in spec.files or "frontend/main.tsx" in spec.files:
            return '<div id="root"></div><script type="module" src="/src/main.tsx"></script>'
        return '<div id="root"></div><script type="module" src="/src/main.jsx"></script>'

    if path == "frontend/src/main.jsx":
        return "import React from 'react';\nimport { createRoot } from 'react-dom/client';\nimport App from './App.jsx';\nimport './styles.css';\ncreateRoot(document.getElementById('root')).render(<App />);\n"

    if path == "frontend/src/main.tsx":
        return "import React from 'react';\nimport { createRoot } from 'react-dom/client';\nimport App from './App';\nimport './styles.css';\n\ncreateRoot(document.getElementById('root') as HTMLElement).render(<React.StrictMode><App /></React.StrictMode>);\n"

    if path == "README.md":
        return f"# {spec.app_name}\n\n{spec.goal}\n\n## Run\n\n```bash\ncd frontend\nnpm install\nnpm run dev\n```\n\n## Build\n\n```bash\ncd frontend\nnpm run build\n```\n"

    if path.endswith(CODE_EXTENSIONS):
        raise RuntimeError(f"No implementation generated for code file {path}; refusing to write filename-only placeholder")

    return f"# {path}\n"


def generate_file(path: str, spec: ProjectSpec, use_ai: bool = True, previous_errors: Optional[list[str]] = None) -> str:
    if should_use_api_builder(path, use_ai):
        built = build_file_with_api(path, spec, previous_errors)
        if built and not is_weak_code(path, built):
            return built
        if path.endswith(CODE_EXTENSIONS):
            raise RuntimeError(f"AI builder failed to produce valid implementation for {path}")

    return fallback_file(path, spec)
