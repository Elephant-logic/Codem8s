from __future__ import annotations

import re
from pathlib import PurePosixPath


def _component_name(path: str) -> str:
    stem = PurePosixPath(path).stem
    return re.sub(r'[^A-Za-z0-9_$]', '', stem) or 'Component'


def _has_default_export(code: str) -> bool:
    return bool(re.search(r'\bexport\s+default\b', code))


def _remove_missing_css_imports(path: str, code: str, files: dict[str, str]) -> str:
    def repl(match: re.Match) -> str:
        import_path = match.group(1)
        if not import_path.endswith('.css'):
            return match.group(0)
        candidate = str(PurePosixPath(path).parent / import_path)
        return match.group(0) if candidate in files else ''
    return re.sub(r"^\s*import\s+['\"]([^'\"]+\.css)['\"];?\s*$", repl, code, flags=re.MULTILINE)


def _ensure_default_component_export(path: str, code: str) -> str:
    if _has_default_export(code):
        return code
    name = _component_name(path)
    if re.search(rf'\bconst\s+{re.escape(name)}\s*=', code) or re.search(rf'\bfunction\s+{re.escape(name)}\s*\(', code):
        return code.rstrip() + f'\nexport default {name};\n'
    match = re.search(r'\bconst\s+([A-Z][A-Za-z0-9_$]*)\s*=', code)
    if match:
        return code.rstrip() + f'\nexport default {match.group(1)};\n'
    return code


def _ensure_data_aliases(path: str, code: str) -> str:
    if path.endswith('/appPlan.js') or path == 'frontend/src/data/appPlan.js':
        if 'APP_PLAN' in code:
            additions: list[str] = []
            if not re.search(r'\bappPlan\b\s*=', code):
                additions.append('const appPlan = APP_PLAN;')
            if not re.search(r'export\s*\{[^}]*appPlan', code):
                additions.append('export { appPlan };')
            if not _has_default_export(code):
                additions.append('export default appPlan;')
            if additions:
                code = code.rstrip() + '\n' + '\n'.join(additions) + '\n'
    if path.endswith('/sampleData.js') or path == 'frontend/src/data/sampleData.js':
        if re.search(r'\bconst\s+sampleData\s*=', code) and not _has_default_export(code):
            code = code.rstrip() + '\nexport default sampleData;\n'
    return code


def deterministic_consistency_repair(files: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    repaired = dict(files)
    logs: list[str] = []
    for path, original in list(repaired.items()):
        if not path.endswith(('.js', '.jsx')):
            continue
        code = original
        code = _remove_missing_css_imports(path, code, repaired)
        code = _ensure_data_aliases(path, code)
        if path.endswith('.jsx') and ('/components/' in path or '/ui/' in path or '/pages/' in path or '/scenes/' in path):
            code = _ensure_default_component_export(path, code)
        if code != original:
            repaired[path] = code
            logs.append(f'Deterministic consistency repair updated {path}')
    return repaired, logs
