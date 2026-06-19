from __future__ import annotations
import ast
import re
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

CODE_EXTENSIONS = (".js", ".jsx", ".py", ".css")


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


def detect_markdown_or_bad_prefix(path: str, content: str) -> List[str]:
    errors: List[str] = []
    if not path.endswith(CODE_EXTENSIONS):
        return errors
    stripped = content.lstrip("\ufeff\n\r\t ")
    if stripped.startswith("```"):
        errors.append("code file starts with markdown fence ```")
    elif stripped.startswith("`"):
        errors.append("code file starts with stray backtick")
    if "```" in stripped:
        errors.append("code file contains markdown fence ```")
    return errors


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


def js_exports(content: str) -> tuple[set[str], bool]:
    named: set[str] = set()
    has_default = bool(re.search(r"\bexport\s+default\b", content))
    for pattern in [
        r"\bexport\s+function\s+([A-Za-z_$][\w$]*)",
        r"\bexport\s+class\s+([A-Za-z_$][\w$]*)",
        r"\bexport\s+const\s+([A-Za-z_$][\w$]*)",
        r"\bexport\s+let\s+([A-Za-z_$][\w$]*)",
        r"\bexport\s+var\s+([A-Za-z_$][\w$]*)",
    ]:
        named.update(re.findall(pattern, content))
    for group in re.findall(r"\bexport\s*\{([^}]+)\}", content, re.S):
        for part in group.split(","):
            token = part.strip()
            if not token:
                continue
            if " as " in token:
                token = token.split(" as ")[-1].strip()
            token = re.sub(r"[^A-Za-z0-9_$].*$", "", token)
            if token:
                named.add(token)
    return named, has_default


def resolve_import_path(from_path: str, import_path: str, files: Dict[str, str]) -> str | None:
    if not import_path.startswith("."):
        return None
    base = PurePosixPath(from_path).parent
    raw = str((base / import_path).as_posix())
    candidates = [raw, raw + ".js", raw + ".jsx", raw + "/index.js", raw + "/index.jsx"]
    for candidate in candidates:
        clean = str(PurePosixPath(candidate))
        if clean in files:
            return clean
    return None


def validate_js_import_exports(files: Dict[str, str]) -> List[str]:
    errors: List[str] = []
    export_cache: dict[str, tuple[set[str], bool]] = {}
    for path, content in files.items():
        if path.endswith((".js", ".jsx")):
            export_cache[path] = js_exports(content)

    for path, content in files.items():
        if not path.endswith((".js", ".jsx")):
            continue

        for names_text, import_path in re.findall(r"import\s*\{([^}]+)\}\s*from\s*['\"]([^'\"]+)['\"]", content):
            target = resolve_import_path(path, import_path, files)
            if not target or target not in export_cache:
                continue
            exported, _ = export_cache[target]
            for raw_name in names_text.split(","):
                name = raw_name.strip()
                if not name:
                    continue
                if " as " in name:
                    name = name.split(" as ")[0].strip()
                if name not in exported:
                    errors.append(f"{path}: imports named export {name} from {target}, but {target} exports {sorted(exported) or 'no named exports'}")

        for default_name, import_path in re.findall(r"import\s+([A-Za-z_$][\w$]*)\s+from\s*['\"]([^'\"]+)['\"]", content):
            if import_path in {"react", "react-dom/client"} or import_path.endswith(".css"):
                continue
            target = resolve_import_path(path, import_path, files)
            if not target or target not in export_cache:
                continue
            _, has_default = export_cache[target]
            if not has_default:
                errors.append(f"{path}: imports default {default_name} from {target}, but {target} has no default export")
    return errors


def validate_file(path: str, content: str, spec_files: Dict[str, str]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not safe_path(path):
        errors.append("unsafe path")
    if path not in spec_files:
        errors.append("file is not in locked manifest")
    if len(content.strip()) < 20:
        errors.append("file is too small to be useful")
    errors.extend(detect_markdown_or_bad_prefix(path, content))
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
    errors.extend(validate_js_import_exports(files))
    return len(errors) == 0, errors
