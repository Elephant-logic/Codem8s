from __future__ import annotations
import ast
from pathlib import PurePosixPath
from typing import Dict, List, Tuple

BANNED_PHRASES = [
    "TODO", "NotImplementedError", "implementation here", "your code here",
    "example only", "dummy data", "lorem ipsum", "pass #", "stub"
]

REQUIRED_EXPORTS = {
    "backend/main.py": ["app"],
    "backend/generator.py": ["build_spec", "generate_file"],
    "backend/validator.py": ["validate_file", "detect_placeholders"],
    "backend/settings.py": ["load_settings", "save_settings", "settings_status"],
}

def safe_path(path: str) -> bool:
    p = PurePosixPath(path)
    return not path.startswith("/") and ".." not in p.parts and len(path.strip()) > 0

def detect_placeholders(content: str) -> List[str]:
    found = []
    lowered = content.lower()
    for phrase in BANNED_PHRASES:
        if phrase.lower() in lowered:
            found.append(phrase)
    return found

def validate_python(content: str) -> List[str]:
    try:
        ast.parse(content)
        return []
    except SyntaxError as exc:
        return [f"SyntaxError line {exc.lineno}: {exc.msg}"]

def exported_names(content: str) -> set[str]:
    names = set()
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return names
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names

def validate_file(path: str, content: str, spec_files: Dict[str, str]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not safe_path(path):
        errors.append("unsafe path")
    if path not in spec_files:
        errors.append("file is not in locked manifest")
    if len(content.strip()) < 20:
        errors.append("file is too small to be useful")
    if not path.endswith("validator.py"):
        for phrase in detect_placeholders(content):
            errors.append(f"banned placeholder phrase: {phrase}")
    if path.endswith(".py"):
        errors.extend(validate_python(content))
        required = REQUIRED_EXPORTS.get(path, [])
        names = exported_names(content)
        for name in required:
            if name not in names:
                errors.append(f"missing required export: {name}")
    return len(errors) == 0, errors

def validate_project_against_spec(files: Dict[str, str], spec_files: Dict[str, str]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    for path in spec_files:
        if path not in files:
            errors.append(f"missing file: {path}")
    for path, content in files.items():
        ok, file_errors = validate_file(path, content, spec_files)
        if not ok:
            errors.extend([f"{path}: {err}" for err in file_errors])
    return len(errors) == 0, errors
