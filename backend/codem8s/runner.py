from __future__ import annotations
import py_compile
from pathlib import Path
from typing import List

def check_python_file(path: str) -> List[str]:
    try:
        py_compile.compile(path, doraise=True)
        return []
    except Exception as exc:
        return [str(exc)]

def smoke_check_tree(root: str) -> List[str]:
    errors: List[str] = []
    for file in Path(root).rglob("*.py"):
        errors.extend([f"{file}: {err}" for err in check_python_file(str(file))])
    return errors
