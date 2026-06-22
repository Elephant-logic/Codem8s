from __future__ import annotations

import os
import shutil
import subprocess
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
            output = (
                f"Command not found: {cmd[0]}\n"
                "Live builds require the Docker backend image with Node/npm installed. "
                "Deploy the backend using the repository Dockerfile, not the Python buildpack.\n"
                f"{exc}"
            )
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

    def install_and_build(self) -> bool:
        frontend = self.root / "frontend"
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
        self.last_error = ""
        self.add_log("Build passed")
        self.add_log(f"Preview copied to {self.preview_path}")
        self.add_log(f"Preview available at {self.preview_url}")
        return True

    def stop(self) -> None:
        self.running = False
        self.add_log("Sandbox preview marked stopped")

    def status(self) -> dict[str, Any]:
        self.running = self.build_ok and self.preview_path.exists()
        return {
            "project_id": self.project_id,
            "running": self.running,
            "build_ok": self.build_ok,
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
        return {"project_id": project_id, "running": False, "build_ok": False, "preview_url": "", "last_error": "No sandbox session", "log_count": 0}
    return session.status()


def sandbox_logs(project_id: str, limit: int = 200) -> dict[str, Any]:
    session = SESSIONS.get(project_id)
    if not session:
        return {"project_id": project_id, "logs": ["No sandbox session"]}
    return {"project_id": project_id, "logs": session.logs[-limit:]}
