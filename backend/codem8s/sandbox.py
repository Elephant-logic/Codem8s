from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from .models import BuildState


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
        self.dev_process: subprocess.Popen[str] | None = None
        self.created_at = time.time()

    def add_log(self, text: str) -> None:
        for line in text.splitlines():
            self.logs.append(line[-2000:])
        self.logs = self.logs[-800:]

    def write_files(self, state: BuildState) -> None:
        for path, item in state.files.items():
            if not item.content:
                continue
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item.content, encoding="utf-8")
        self.add_log(f"Wrote project files to {self.root}")

    def run(self, cmd: list[str], cwd: Path, timeout: int = 180) -> tuple[bool, str]:
        self.add_log("$ " + " ".join(cmd))
        try:
            proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, timeout=timeout)
            output = (proc.stdout or "") + "\n" + (proc.stderr or "")
            self.add_log(output)
            return proc.returncode == 0, output
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
        ok, out = self.run(["npm", "install", "--silent"], frontend, timeout=240)
        if not ok:
            self.last_error = out[-8000:]
            return False
        ok, out = self.run(["npm", "run", "build"], frontend, timeout=240)
        self.build_ok = ok
        if not ok:
            self.last_error = out[-8000:]
        else:
            self.last_error = ""
            self.add_log("Build passed")
        return ok

    def start_dev(self, port: int) -> None:
        frontend = self.root / "frontend"
        if not frontend.exists():
            self.add_log("No frontend folder found; cannot start preview")
            return
        if self.dev_process and self.dev_process.poll() is None:
            self.add_log("Preview already running")
            return
        cmd = ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", str(port)]
        self.add_log("$ " + " ".join(cmd))
        self.dev_process = subprocess.Popen(cmd, cwd=str(frontend), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.running = True
        self.preview_url = f"http://localhost:{port}"

        def reader() -> None:
            assert self.dev_process and self.dev_process.stdout
            for line in self.dev_process.stdout:
                self.add_log(line.rstrip())

        threading.Thread(target=reader, daemon=True).start()

    def stop(self) -> None:
        if self.dev_process and self.dev_process.poll() is None:
            self.dev_process.terminate()
            try:
                self.dev_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.dev_process.kill()
        self.running = False
        self.add_log("Sandbox stopped")

    def status(self) -> dict[str, Any]:
        alive = bool(self.dev_process and self.dev_process.poll() is None)
        self.running = alive
        return {
            "project_id": self.project_id,
            "running": self.running,
            "build_ok": self.build_ok,
            "preview_url": self.preview_url,
            "last_error": self.last_error[-4000:],
            "root": str(self.root),
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
    session.start_dev(port)
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
