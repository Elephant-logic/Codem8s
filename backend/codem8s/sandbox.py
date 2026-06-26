from __future__ import annotations

import html
import os
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
            output = f"Command not found: {cmd[0]}\nLive builds require the Docker backend image with the required runtime installed.\n{exc}"
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

    def _copy_preview_dir(self, source: Path, index_file: str = "index.html") -> None:
        if self.preview_path.exists():
            shutil.rmtree(self.preview_path, ignore_errors=True)
        self.preview_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, self.preview_path)
        self.preview_url = f"/preview/{self.project_id}/{index_file}"
        self.running = True
        self.build_ok = True
        self.runtime_ok = True
        self.last_error = ""
        self.add_log(f"Preview copied to {self.preview_path}")
        self.add_log(f"Preview available at {self.preview_url}")

    def _standalone_html_preview(self) -> bool:
        html_files = sorted(self.root.rglob("*.html"), key=lambda p: (0 if p.name.lower() == "index.html" else 1, len(p.as_posix())))
        if not html_files:
            return False
        chosen = html_files[0]
        preview_src = self.root / "__codem8s_standalone_preview"
        if preview_src.exists():
            shutil.rmtree(preview_src, ignore_errors=True)
        preview_src.mkdir(parents=True, exist_ok=True)
        # Copy all local assets/text files so relative links keep working for one-file or small static apps.
        for source in self.root.rglob("*"):
            if not source.is_file() or "__codem8s_standalone_preview" in source.parts:
                continue
            rel = source.relative_to(self.root)
            target = preview_src / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        rel_index = chosen.relative_to(self.root).as_posix()
        self._copy_preview_dir(preview_src, rel_index)
        self.add_log(f"Standalone HTML preview: {rel_index}")
        return True

    def _standalone_python_preview(self) -> bool:
        py_files = sorted(self.root.rglob("*.py"), key=lambda p: (0 if p.name in {"main.py", "app.py"} else 1, len(p.as_posix())))
        if not py_files:
            return False
        chosen = py_files[0]
        ok, out = self.run(["python", "-m", "py_compile", str(chosen.relative_to(self.root))], self.root, timeout=30)
        if not ok:
            self.last_error = out[-8000:]
            self.build_ok = False
            return True
        preview_src = self.root / "__codem8s_python_preview"
        if preview_src.exists():
            shutil.rmtree(preview_src, ignore_errors=True)
        preview_src.mkdir(parents=True, exist_ok=True)
        code = chosen.read_text(encoding="utf-8", errors="replace")
        index = preview_src / "index.html"
        index.write_text(
            "<!doctype html><meta charset='utf-8'><title>Codem8s Python Preview</title>"
            "<style>body{margin:0;background:#0b1020;color:#e8ecff;font-family:Inter,system-ui,Arial;padding:24px}pre{white-space:pre-wrap;background:#090d1a;border:1px solid #33406e;border-radius:12px;padding:16px;overflow:auto}.ok{color:#93f5b5}</style>"
            f"<h1>Python file preview</h1><p class='ok'>Syntax check passed for <b>{html.escape(chosen.relative_to(self.root).as_posix())}</b>.</p>"
            f"<pre>{html.escape(code)}</pre>",
            encoding="utf-8",
        )
        self._copy_preview_dir(preview_src)
        self.add_log(f"Standalone Python preview: {chosen.relative_to(self.root).as_posix()}")
        return True

    def browser_smoke_check(self, frontend: Path) -> tuple[bool, str]:
        if os.getenv("CODEM8S_SKIP_BROWSER_SMOKE", "").lower() in {"1", "true", "yes"}:
            return True, "Browser smoke check skipped"
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
            const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
            const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
            const errors = [];
            page.on('pageerror', err => errors.push('pageerror: ' + err.message));
            page.on('console', msg => { if (msg.type() === 'error') errors.push('console error: ' + msg.text()); });
            await page.goto(`http://127.0.0.1:${server.address().port}/index.html`, { waitUntil: 'networkidle', timeout: 15000 });
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
            if (errors.length) { console.error(errors.join('\n')); process.exit(2); }
            console.log(`Browser smoke passed: text=${visibleText.length} canvas=${canvasCount} buttons=${buttonCount}`);
        """), encoding="utf-8")
        ok, out = self.run(["node", str(smoke.name)], frontend, timeout=90)
        if ok:
            return True, out or "Browser smoke check passed"
        if "Cannot find package 'playwright'" in out or "Cannot find module 'playwright'" in out or "ERR_MODULE_NOT_FOUND" in out:
            self.add_log("Browser smoke unavailable: Playwright is not installed")
            return True, "Browser smoke unavailable: Playwright is not installed"
        return False, out[-8000:]

    def install_and_build(self) -> bool:
        frontend = self.root / "frontend"
        self.runtime_ok = False
        if not frontend.exists():
            if self._standalone_html_preview():
                self.add_log("No frontend folder found; served standalone HTML/static app instead")
                return True
            if self._standalone_python_preview():
                self.add_log("No frontend folder found; served Python code preview after syntax check")
                return self.build_ok
            self.last_error = "No frontend folder found and no standalone .html or .py file could be previewed"
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
        self._copy_preview_dir(dist)
        self.add_log("Build passed")
        return True

    def stop(self) -> None:
        self.running = False
        self.add_log("Sandbox stopped")

    def status(self) -> dict[str, Any]:
        return {"project_id": self.project_id, "running": self.running, "build_ok": self.build_ok, "runtime_ok": self.runtime_ok, "root": str(self.root), "preview_url": self.preview_url, "last_error": self.last_error, "logs": self.logs[-300:]}


SESSIONS: dict[str, SandboxSession] = {}


def start_sandbox(state: BuildState) -> dict[str, Any]:
    old = SESSIONS.get(state.project_id)
    if old:
        old.stop()
    session = SandboxSession(state.project_id)
    SESSIONS[state.project_id] = session
    session.write_files(state)
    session.install_and_build()
    return session.status()


def stop_sandbox(project_id: str) -> dict[str, Any]:
    session = SESSIONS.get(project_id)
    if not session:
        return {"running": False, "logs": ["No sandbox session"]}
    session.stop()
    return session.status()


def sandbox_status(project_id: str) -> dict[str, Any]:
    session = SESSIONS.get(project_id)
    if not session:
        return {"running": False, "build_ok": False, "runtime_ok": False, "logs": ["No sandbox session"]}
    return session.status()


def sandbox_logs(project_id: str, limit: int = 200) -> dict[str, Any]:
    data = sandbox_status(project_id)
    data["logs"] = data.get("logs", [])[-limit:]
    return data
