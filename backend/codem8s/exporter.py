from __future__ import annotations
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from .models import BuildState

EXPORT_DIR = Path("exports")

def export_project(state: BuildState) -> str:
    EXPORT_DIR.mkdir(exist_ok=True)
    zip_path = EXPORT_DIR / f"{state.project_id}.zip"
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as zf:
        for path, item in state.files.items():
            if item.status == "valid" and item.content:
                zf.writestr(path, item.content)
        zf.writestr("codem8s_spec.json", state.spec.model_dump_json(indent=2))
    return str(zip_path)
