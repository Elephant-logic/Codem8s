from __future__ import annotations

from typing import Dict

from .models import ProjectSpec


def repair_project(spec: ProjectSpec, files: Dict[str, str]) -> Dict[str, str]:
    """Whole-project quality repair hook.

    This module exists so codem8s.main can import cleanly on Render.
    The real compile/npm build repair loop runs from agent_build_repair.py.

    Keep this hook safe: it must never crash app startup or export.
    """
    return dict(files)
