from __future__ import annotations

import json
import re
from pathlib import PurePosixPath
from typing import Optional

from .models import ProjectSpec
from .agent_blueprint import apply_instruction, build_spec
from .factory_renderer import render_file
from .agent_builder import build_file_with_api, is_weak_code

API_FIRST_EXTENSIONS = (".jsx", ".js", ".tsx", ".ts", ".css", ".py")
CODE_EXTENSIONS = (".jsx", ".js", ".tsx", ".ts", ".css", ".py")
KNOWN_OPTIONAL_DEPS = {
    "zustand": "latest",
    "react-router-dom": "latest",
    "lucide-react": "latest",
    "framer-motion": "latest",
    "date-fns": "latest",
    "clsx": "latest",
    "nanoid": "latest",
}


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
    return "route" in text or "router" in text or "frontend/src/routes" in text


def _planned_package_dependencies(spec: ProjectSpec) -> dict[str, str]:
    text = (spec.goal + "\n" + json.dumps(spec.files) + "\n" + "\n".join(spec.change_log)).lower()
    deps = {"@vitejs/plugin-react": "latest", "vite": "latest", "react": "latest", "react-dom": "latest"}
    if _spec_uses_tsx(spec):
        deps.update({"typescript": "latest", "@types/react": "latest", "@types/react-dom": "latest"})
    if _spec_uses_router(spec):
        deps["react-router-dom"] = "latest"
    for pkg, version in KNOWN_OPTIONAL_DEPS.items():
        if pkg.lower() in text:
            deps[pkg] = version
    if "store/" in text or "gamestore" in text or "zustand" in text:
        deps["zustand"] = "latest"
    return deps


def _safe_identifier(value: str, fallback: str = "GeneratedModule") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", value)
    if not cleaned:
        cleaned = fallback
    if cleaned[0].isdigit():
        cleaned = fallback + cleaned
    return cleaned


def _export_names_for_path(path: str, spec: ProjectSpec) -> list[str]:
    purpose = spec.files.get(path, "")
    match = re.search(r"exports=\[([^\]]*)\]", purpose)
    if match:
        names = [_safe_identifier(part.strip().strip("'\""), "generated") for part in match.group(1).split(",") if part.strip().strip("'\"")]
        if names:
            return names
    stem = PurePosixPath(path).stem
    if path.endswith((".jsx", ".tsx")):
        return [_safe_identifier(stem[:1].upper() + stem[1:], "GeneratedComponent")]
    return []


def resilient_code_fallback(path: str, spec: ProjectSpec, reason: str = "AI generation failed") -> str:
    name = (_export_names_for_path(path, spec) or [_safe_identifier(PurePosixPath(path).stem, "generated")])[0]
    app_name = spec.app_name.replace("'", "")
    goal = spec.goal.replace("`", "").replace("${", "")[:500]
    safe_reason = reason.replace("'", "").replace("\n", " ")[:200]

    if path.endswith(".css"):
        return """
:root { color-scheme: dark; font-family: Inter, system-ui, sans-serif; background: #07111f; color: #eaf2ff; }
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; background: linear-gradient(135deg, #07111f, #13243d 52%, #07111f); }
button { border: 0; border-radius: 12px; padding: 0.8rem 1rem; background: #6d7cff; color: white; font-weight: 700; cursor: pointer; box-shadow: 0 14px 30px rgba(0,0,0,.28); }
button:hover { filter: brightness(1.08); }
.app-shell, .screen, .page { min-height: 100vh; padding: 24px; display: grid; gap: 18px; }
.panel, .card, .toolbar, .hud, .map-wrap { border: 1px solid rgba(255,255,255,.12); border-radius: 22px; background: rgba(12, 22, 40, .82); box-shadow: 0 22px 70px rgba(0,0,0,.35); padding: 18px; }
.grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); }
canvas { width: 100%; min-height: 420px; border-radius: 18px; background: #14261d; border: 1px solid rgba(255,255,255,.14); }
.badge { display: inline-flex; padding: 6px 10px; border-radius: 999px; background: rgba(125, 211, 252, .18); color: #bae6fd; }
""".strip() + "\n"

    if path.endswith((".jsx", ".tsx")):
        return f"""import React, {{ useState }} from 'react';

export function {name}() {{
  const [tick, setTick] = useState(0);
  const metrics = [
    {{ label: 'System status', value: 'online' }},
    {{ label: 'Simulation tick', value: tick }},
    {{ label: 'Active module', value: '{name}' }}
  ];
  return (
    <section className="panel" data-generated-fallback="{name}">
      <header>
        <span className="badge">Recovered module</span>
        <h2>{name}</h2>
        <p>{app_name}: {goal}</p>
      </header>
      <div className="grid">
        {{metrics.map((metric) => (
          <article className="card" key={{metric.label}}>
            <strong>{{metric.label}}</strong>
            <p>{{metric.value}}</p>
          </article>
        ))}}
      </div>
      <button type="button" onClick={{() => setTick((value) => value + 1)}}>Run {name} action</button>
    </section>
  );
}}

export default {name};
"""

    if path.endswith((".ts", ".js")):
        exports = _export_names_for_path(path, spec) or [name]
        flat: list[str] = []
        for export_name in exports[:8]:
            flat.extend([
                f"export const {export_name} = {{",
                f"  name: '{export_name}',",
                "  status: 'ready',",
                f"  reason: '{safe_reason}',",
                "  updatedAt: new Date().toISOString(),",
                "  records: []",
                "};",
                "",
            ])
        flat.append("export function createRecoveredState(seed = {}) {")
        flat.append("  return { ...seed, recovered: true, updatedAt: new Date().toISOString() };")
        flat.append("}")
        return "\n".join(flat).strip() + "\n"

    if path.endswith(".py"):
        func = _safe_identifier(PurePosixPath(path).stem, "generated_module").lower()
        return f"""from __future__ import annotations


def {func}_status() -> dict:
    return {{"module": "{path}", "status": "ready", "reason": "{safe_reason}"}}
"""

    raise RuntimeError(f"No implementation generated for code file {path}; refusing to write filename-only placeholder")


def fallback_file(path: str, spec: ProjectSpec) -> str:
    rendered = render_file(path, spec)
    if rendered is not None:
        return rendered

    if path == "backend/requirements.txt":
        return "fastapi==0.111.0\nuvicorn[standard]==0.30.1\npydantic==2.7.4\npython-dotenv==1.0.1\n"

    if path == "frontend/package.json":
        return json.dumps({"scripts": {"dev": "vite --host 0.0.0.0", "build": "vite build", "preview": "vite preview"}, "dependencies": _planned_package_dependencies(spec), "devDependencies": {}}, separators=(",", ":"))

    if path == "frontend/index.html":
        if "frontend/src/main.tsx" in spec.files:
            return '<div id="root"></div><script type="module" src="/src/main.tsx"></script>'
        return '<div id="root"></div><script type="module" src="/src/main.jsx"></script>'

    if path == "frontend/src/main.jsx":
        return "import React from 'react';\nimport { createRoot } from 'react-dom/client';\nimport App from './App.jsx';\nimport './styles.css';\ncreateRoot(document.getElementById('root')).render(<App />);\n"

    if path == "frontend/src/main.tsx":
        return "import React from 'react';\nimport { createRoot } from 'react-dom/client';\nimport App from './App';\nimport './styles.css';\n\nconst container = document.getElementById('root');\nif (!container) throw new Error('Root element #root was not found');\ncreateRoot(container).render(<React.StrictMode><App /></React.StrictMode>);\n"

    if path == "README.md":
        return f"# {spec.app_name}\n\n{spec.goal}\n\n## Run\n\n```bash\ncd frontend\nnpm install\nnpm run dev\n```\n\n## Build\n\n```bash\ncd frontend\nnpm run build\n```\n"

    if path.endswith(CODE_EXTENSIONS):
        return resilient_code_fallback(path, spec, reason="factory fallback")

    return f"# {path}\n"


def generate_file(path: str, spec: ProjectSpec, use_ai: bool = True, previous_errors: Optional[list[str]] = None) -> str:
    if should_use_api_builder(path, use_ai):
        built = build_file_with_api(path, spec, previous_errors)
        if built and not is_weak_code(path, built):
            return built
        if path.endswith(CODE_EXTENSIONS):
            return resilient_code_fallback(path, spec, reason="AI builder failed or returned weak code")

    return fallback_file(path, spec)
