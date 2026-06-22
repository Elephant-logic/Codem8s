from __future__ import annotations

import os
import re
import shutil
import subprocess
import textwrap
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from .models import BuildState

DATA_DIR = Path(os.environ.get("CODEM8S_DATA_DIR", "/opt/render/.codem8s"))
PREVIEW_ROOT = Path(os.environ.get("CODEM8S_PREVIEW_DIR", str(DATA_DIR / "previews")))


def ensure_preview_root() -> Path:
    PREVIEW_ROOT.mkdir(parents=True, exist_ok=True)
    return PREVIEW_ROOT


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def scan_runtime_risks(frontend: Path) -> list[str]:
    src = frontend / "src"
    if not src.exists():
        return []
    files = {path.relative_to(src).as_posix(): _read(path) for path in src.rglob("*") if path.suffix in {".js", ".jsx", ".ts", ".tsx"}}
    risks: list[str] = []

    for rel, text in files.items():
        for match in re.finditer(r"const\s*\{([^}]+)\}\s*=\s*(use[A-Z][A-Za-z0-9_]*)\s*\(", text):
            requested = [part.split(":", 1)[0].strip() for part in match.group(1).split(",") if part.strip()]
            hook = match.group(2)
            hook_file = next((body for _name, body in files.items() if f"function {hook}" in body or f"const {hook}" in body or f"export function {hook}" in body), "")
            if not hook_file:
                continue
            returned_names = set()
            for ret in re.finditer(r"return\s*\{([^}]+)\}", hook_file, flags=re.S):
                returned_names.update(part.split(":", 1)[0].strip() for part in ret.group(1).replace("\n", " ").split(",") if part.strip())
            if returned_names:
                missing = [name for name in requested if name not in returned_names]
                if missing:
                    risks.append(f"{rel}: hook {hook} is destructured for {missing}, but hook returns {sorted(returned_names)}. This can crash the preview before render.")

    for rel, text in files.items():
        for obj, method in re.findall(r"\b([A-Z][A-Za-z0-9_]+)\.([A-Za-z_][A-Za-z0-9_]*)\s*\(", text):
            target_body = next((body for _name, body in files.items() if f"const {obj}" in body or f"class {obj}" in body or f"function {obj}" in body), "")
            if not target_body:
                continue
            if f"{method}:" not in target_body and f"{method}(" not in target_body and f"function {method}" not in target_body:
                risks.append(f"{rel}: calls {obj}.{method}(), but {obj} does not define/export that method. This can blank the preview at runtime.")

    component_defs: dict[str, tuple[str, str, list[str]]] = {}
    for rel, text in files.items():
        for comp, params in re.findall(r"const\s+([A-Z][A-Za-z0-9_]*)\s*=\s*\(([^)]*)\)\s*=>", text):
            props = [p.strip().split("=", 1)[0].strip() for p in params.strip("{} ").split(",") if p.strip()]
            if props:
                component_defs[comp] = (rel, text, props)
        for comp, params in re.findall(r"function\s+([A-Z][A-Za-z0-9_]*)\s*\(([^)]*)\)", text):
            props = [p.strip().split("=", 1)[0].strip() for p in params.strip("{} ").split(",") if p.strip()]
            if props:
                component_defs[comp] = (rel, text, props)

    for rel, text in files.items():
        for comp, (def_rel, def_text, props) in component_defs.items():
            if re.search(rf"<{comp}\s*/>", text):
                unsafe = []
                for prop in props:
                    if re.search(rf"\b{prop}\.([A-Za-z_][A-Za-z0-9_]*)", def_text) or re.search(rf"\b{prop}\s*<|\b{prop}\s*\+|\b{prop}\.toLowerCase\(", def_text):
                        unsafe.append(prop)
                if unsafe:
                    risks.append(f"{rel}: renders <{comp} /> without props, but {def_rel} dereferences required props {unsafe}. This can blank the preview.")

    for rel, text in files.items():
        for var in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\.toLowerCase\(\)", text):
            if not re.search(rf"{var}\s*=\s*['\"`]", text) and not re.search(rf"{var}\s*\?\.toLowerCase", text):
                risks.append(f"{rel}: calls {var}.toLowerCase() without a default/null guard. This can crash when prop/state is undefined.")

    seen = set()
    unique = []
    for risk in risks:
        if risk not in seen:
            seen.add(risk)
            unique.append(risk)
    return unique[:20]


class SandboxSession:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.tmp = TemporaryDirectory(prefix=f"codem8s_live_{project_id}_")
        self.root = Path(self.tmp.name)
        self.logs: list[str] = []
        self.running = False
        self.build_ok = False
        self.runtime_ok = False
        self.last_error = ""
        self.preview_url = ""
        self.preview_path = ensure_preview_root() / project_id
        self.created_at = time.time()

    def add_log(self, text: str) -> None:
        for line in str(text).splitlines():
            self.logs.append(line[-2500:])
        self.logs = self.logs[-1200:]

    def write_files(self, state: BuildState) -> None:
        if self.root.exists():
            for item in self.root.iterdir():
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
        for path, item in state.files.items():
            if not item.content:
                continue
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item.content, encoding="utf-8")
        self.add_log(f"Wrote project files to {self.root}")

    def run(self, cmd: list[str], cwd: Path, timeout: int = 240) -> tuple[bool, str]:
        self.add_log("$ " + " ".join(cmd))
        try:
            proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, timeout=timeout)
            output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
            self.add_log(output or f"Command exited {proc.returncode}")
            return proc.returncode == 0, output
        except FileNotFoundError as exc:
            output = f"Command not found: {cmd[0]}\nLive builds require the Docker backend image with Node/npm installed.\n{exc}"
            self.add_log(output)
            return False, output
        except subprocess.TimeoutExpired as exc:
            output = f"Timed out: {' '.join(cmd)}\n{exc}"
            self.add_log(output)
            return False, output
        except Exception as exc:
            output = f"Failed: {' '.join(cmd)}\n{exc}"
            self.add_log(output)
            return False, output

    def browser_smoke_check(self, frontend: Path) -> tuple[bool, str]:
        if os.getenv("CODEM8S_SKIP_BROWSER_SMOKE", "").lower() in {"1", "true", "yes"}:
            return True, "Browser smoke check skipped by CODEM8S_SKIP_BROWSER_SMOKE"

        smoke = frontend / "codem8s-smoke.mjs"
        smoke.write_text(textwrap.dedent("""
            import { chromium } from 'playwright';
            import http from 'node:http';
            import fs from 'node:fs';
            import path from 'node:path';
            import { fileURLToPath } from 'node:url';

            const root = path.join(path.dirname(fileURLToPath(import.meta.url)), 'dist');
            const mime = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.png': 'image/png', '.svg': 'image/svg+xml', '.json': 'application/json' };
            const server = http.createServer((req, res) => {
              let urlPath = decodeURIComponent((req.url || '/').split('?')[0]);
              if (urlPath === '/') urlPath = '/index.html';
              const target = path.normalize(path.join(root, urlPath));
              if (!target.startsWith(root)) { res.writeHead(403); res.end('forbidden'); return; }
              if (!fs.existsSync(target)) { res.writeHead(404); res.end('not found'); return; }
              res.writeHead(200, { 'Content-Type': mime[path.extname(target)] || 'application/octet-stream' });
              fs.createReadStream(target).pipe(res);
            });
            await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
            const port = server.address().port;
            const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
            const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
            const errors = [];
            page.on('pageerror', err => errors.push('pageerror: ' + err.message));
            page.on('console', msg => { if (['error', 'warning'].includes(msg.type())) errors.push('console ' + msg.type() + ': ' + msg.text()); });
            await page.goto(`http://127.0.0.1:${port}/index.html`, { waitUntil: 'networkidle', timeout: 15000 });
            await page.waitForTimeout(1200);
            const visibleText = (await page.locator('body').innerText().catch(() => '')).trim();
            const canvasCount = await page.locator('canvas').count().catch(() => 0);
            const buttonCount = await page.locator('button').count().catch(() => 0);
            const bodyBox = await page.locator('body').boundingBox().catch(() => null);
            if (!bodyBox || bodyBox.width < 50 || bodyBox.height < 50) errors.push('body did not render a visible layout');
            if (visibleText.length < 20 && canvasCount === 0) errors.push('page rendered almost no visible text and no canvas');
            if (buttonCount > 0) {
              await page.locator('button').first().click({ timeout: 2000 }).catch(err => errors.push('first button click failed: ' + err.message));
              await page.waitForTimeout(300);
            }
            await browser.close();
            server.close();
            if (errors.length) {
              console.error(errors.join('\n'));
              process.exit(2);
            }
            console.log(`Browser smoke passed: text=${visibleText.length} canvas=${canvasCount} buttons=${buttonCount}`);
        """), encoding="utf-8")

        ok, out = self.run(["node", str(smoke.name)], frontend, timeout=90)
        if ok:
            return True, out or "Browser smoke check passed"
        if "Cannot find package 'playwright'" in out or "Cannot find module 'playwright'" in out or "ERR_MODULE_NOT_FOUND" in out:
            self.add_log("Browser smoke unavailable: install Playwright in Docker image to enable real runtime verification")
            return True, "Browser smoke unavailable: Playwright is not installed"
        return False, out[-8000:]

    def install_and_build(self) -> bool:
        frontend = self.root / "frontend"
        self.runtime_ok = False
        if not frontend.exists():
            self.last_error = "No frontend folder found"
            self.add_log(self.last_error)
            return False

        ok, out = self.run(["node", "--version"], frontend, timeout=30)
        if not ok:
            self.last_error = out[-8000:]
            self.build_ok = False
            return False
        self.run(["npm", "--version"], frontend, timeout=30)

        install_cmd = ["npm", "ci", "--silent"] if (frontend / "package-lock.json").exists() else ["npm", "install", "--silent"]
        ok, out = self.run(install_cmd, frontend, timeout=360)
        if not ok:
            self.last_error = out[-8000:]
            self.build_ok = False
            return False

        ok, out = self.run(["npm", "run", "build", "--", "--base", "./"], frontend, timeout=360)
        self.build_ok = ok
        if not ok:
            self.last_error = out[-8000:]
            self.running = False
            return False

        runtime_risks = scan_runtime_risks(frontend)
        if runtime_risks:
            self.build_ok = False
            self.runtime_ok = False
            self.running = False
            self.last_error = "Runtime preview risk: build passed but app is likely to blank-screen.\n" + "\n".join(runtime_risks)
            self.add_log(self.last_error)
            self.add_log("Preview blocked until runtime risks are repaired")
            return False

        smoke_ok, smoke_out = self.browser_smoke_check(frontend)
        if not smoke_ok:
            self.build_ok = False
            self.runtime_ok = False
            self.running = False
            self.last_error = "Browser runtime check failed after build.\n" + smoke_out
            self.add_log(self.last_error)
            self.add_log("Preview blocked until browser runtime errors are repaired")
            return False
        self.add_log(smoke_out)

        dist = frontend / "dist"
        if not dist.exists():
            self.last_error = "Build completed but frontend/dist was not created"
            self.add_log(self.last_error)
            self.build_ok = False
            self.running = False
            return False

        if self.preview_path.exists():
            shutil.rmtree(self.preview_path, ignore_errors=True)
        self.preview_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(dist, self.preview_path)
        self.preview_url = f"/preview/{self.project_id}/index.html"
        self.running = True
        self.build_ok = True
        self.runtime_ok = True
        self.last_error = ""
        self.add_log("Build passed")
        self.add_log("Runtime checks passed")
        self.add_log(f"Preview copied to {self.preview_path}")
        self.add_log(f"Preview available at {self.preview_url}")
        return True

    def stop(self) -> None:
        self.running = False
        self.add_log("Sandbox preview marked stopped")

    def status(self) -> dict[str, Any]:
        self.running = self.build_ok and self.runtime_ok and self.preview_path.exists()
        return {
            "project_id": self.project_id,
            "running": self.running,
            "build_ok": self.build_ok,
            "runtime_ok": self.runtime_ok,
            "preview_url": self.preview_url,
            "last_error": self.last_error[-4000:],
            "root": str(self.root),
            "preview_path": str(self.preview_path),
            "log_count": len(self.logs),
        }


SESSIONS: dict[str, SandboxSession] = {}


def get_or_create_session(state: BuildState) -> SandboxSession:
    session = SESSIONS.get(state.project_id)
    if not session:
        session = SandboxSession(state.project_id)
        SESSIONS[state.project_id] = session
    return session


def start_sandbox(state: BuildState, port: int = 5173) -> dict[str, Any]:
    session = get_or_create_session(state)
    session.write_files(state)
    session.install_and_build()
    return session.status()


def stop_sandbox(project_id: str) -> dict[str, Any]:
    session = SESSIONS.get(project_id)
    if not session:
        return {"project_id": project_id, "running": False, "message": "No sandbox session"}
    session.stop()
    return session.status()


def sandbox_status(project_id: str) -> dict[str, Any]:
    session = SESSIONS.get(project_id)
    if not session:
        return {"project_id": project_id, "running": False, "build_ok": False, "runtime_ok": False, "preview_url": "", "last_error": "No sandbox session", "log_count": 0}
    return session.status()


def sandbox_logs(project_id: str, limit: int = 200) -> dict[str, Any]:
    session = SESSIONS.get(project_id)
    if not session:
        return {"project_id": project_id, "logs": ["No sandbox session"]}
    return {"project_id": project_id, "logs": session.logs[-limit:]}
