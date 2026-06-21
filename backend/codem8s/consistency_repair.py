from __future__ import annotations

import re
from pathlib import PurePosixPath


IMPORT_RE = re.compile(r"(import\s+(?P<what>[^;\n]+?)\s+from\s+['\"])(?P<spec>[^'\"]+)(['\"];?)")
EXPORT_NAMED_RE = re.compile(r"export\s*\{(?P<names>[^}]+)\}")
EXPORT_DECL_RE = re.compile(r"export\s+(?:class|function|const|let|var)\s+(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)")


def _component_name(path: str) -> str:
    stem = PurePosixPath(path).stem
    return re.sub(r'[^A-Za-z0-9_$]', '', stem) or 'Component'


def _has_default_export(code: str) -> bool:
    return bool(re.search(r'\bexport\s+default\b', code))


def _normalise(path: PurePosixPath) -> str:
    parts: list[str] = []
    for part in path.parts:
        if part in ('', '.'):
            continue
        if part == '..':
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return '/'.join(parts)


def _with_extensions(candidate: str) -> list[str]:
    suffix = PurePosixPath(candidate).suffix
    if suffix:
        return [candidate]
    return [candidate + ext for ext in ('.js', '.jsx', '.ts', '.tsx', '.css', '/index.js', '/index.jsx')]


def _resolve_relative(path: str, spec: str, files: dict[str, str]) -> str | None:
    base = PurePosixPath(path).parent
    raw = _normalise(base / spec)
    for candidate in _with_extensions(raw):
        if candidate in files:
            return candidate
    return None


def _relative_spec(from_path: str, target_path: str) -> str:
    from_parts = PurePosixPath(from_path).parent.parts
    target_parts = PurePosixPath(target_path).parts
    common = 0
    while common < len(from_parts) and common < len(target_parts) and from_parts[common] == target_parts[common]:
        common += 1
    ups = ['..'] * (len(from_parts) - common)
    downs = list(target_parts[common:])
    rel_parts = ups + downs
    if not rel_parts:
        rel = './' + PurePosixPath(target_path).name
    else:
        rel = '/'.join(rel_parts)
        if not rel.startswith('.'):
            rel = './' + rel
    # Vite handles extensionless JS imports, but explicit extensions make generated graphs less ambiguous.
    return rel


def _build_basename_index(files: dict[str, str]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for path in files:
        if path.startswith('frontend/src/') and path.endswith(('.js', '.jsx', '.ts', '.tsx', '.css')):
            index.setdefault(PurePosixPath(path).name.lower(), []).append(path)
            index.setdefault(PurePosixPath(path).stem.lower(), []).append(path)
    return index


def _repair_import_paths(path: str, code: str, files: dict[str, str], logs: list[str]) -> str:
    basename_index = _build_basename_index(files)

    def repl(match: re.Match) -> str:
        prefix, spec, suffix = match.group(1), match.group('spec'), match.group(4)
        if not spec.startswith('.'):
            return match.group(0)
        if _resolve_relative(path, spec, files):
            return match.group(0)
        key = PurePosixPath(spec).name.lower()
        candidates = basename_index.get(key) or basename_index.get(PurePosixPath(key).stem.lower()) or []
        if not candidates:
            return match.group(0)
        # Prefer same broad frontend area but allow crossing from src/game to src/systems/ui.
        candidates = sorted(candidates, key=lambda p: (0 if '/src/' in p else 1, len(p)))
        target = candidates[0]
        new_spec = _relative_spec(path, target)
        logs.append(f'Deterministic import path repair in {path}: {spec} -> {new_spec}')
        return prefix + new_spec + suffix

    return IMPORT_RE.sub(repl, code)


def _remove_missing_css_imports(path: str, code: str, files: dict[str, str]) -> str:
    def repl(match: re.Match) -> str:
        import_path = match.group(1)
        if not import_path.endswith('.css'):
            return match.group(0)
        return match.group(0) if _resolve_relative(path, import_path, files) else ''
    return re.sub(r"^\s*import\s+['\"]([^'\"]+\.css)['\"];?\s*$", repl, code, flags=re.MULTILINE)


def _exported_names(code: str) -> set[str]:
    names = set(EXPORT_DECL_RE.findall(code))
    for match in EXPORT_NAMED_RE.finditer(code):
        for raw in match.group('names').split(','):
            name = raw.strip().split(' as ')[-1].strip()
            if name:
                names.add(name)
    return names


def _local_declared_names(code: str) -> set[str]:
    return set(re.findall(r"\b(?:class|function|const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)", code))


def _imported_named_symbols(import_what: str) -> list[str]:
    m = re.search(r"\{([^}]+)\}", import_what)
    if not m:
        return []
    out = []
    for raw in m.group(1).split(','):
        raw = raw.strip()
        if not raw:
            continue
        out.append(raw.split(' as ')[0].strip())
    return out


def _ensure_missing_named_exports(path: str, code: str, all_files: dict[str, str], logs: list[str]) -> str:
    needed: set[str] = set()
    for importer_path, importer_code in all_files.items():
        if not importer_path.endswith(('.js', '.jsx', '.ts', '.tsx')):
            continue
        for match in IMPORT_RE.finditer(importer_code):
            spec = match.group('spec')
            if not spec.startswith('.'):
                continue
            resolved = _resolve_relative(importer_path, spec, all_files)
            if resolved == path:
                needed.update(_imported_named_symbols(match.group('what')))
    if not needed:
        return code
    exported = _exported_names(code)
    declared = _local_declared_names(code)
    additions: list[str] = []
    for name in sorted(needed - exported):
        if name in declared:
            additions.append(name)
        else:
            # For generated system modules, create an object facade from existing function exports.
            funcs = sorted(n for n in exported if n and n[0].islower())
            if funcs and name.endswith('System') or funcs and name.endswith('Manager'):
                body = ', '.join(funcs)
                code = code.rstrip() + f"\nconst {name} = {{ {body} }};\n"
                additions.append(name)
                declared.add(name)
    if additions:
        code = code.rstrip() + '\nexport { ' + ', '.join(additions) + ' };\n'
        logs.append(f'Deterministic export repair in {path}: added {", ".join(additions)}')
    return code


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
        if not path.endswith(('.js', '.jsx', '.ts', '.tsx')):
            continue
        code = original
        code = _remove_missing_css_imports(path, code, repaired)
        code = _repair_import_paths(path, code, repaired, logs)
        code = _ensure_data_aliases(path, code)
        if path.endswith('.jsx') and ('/components/' in path or '/ui/' in path or '/pages/' in path or '/scenes/' in path):
            code = _ensure_default_component_export(path, code)
        if code != original:
            repaired[path] = code
            logs.append(f'Deterministic consistency repair updated {path}')

    # Second pass after import paths are repaired: make imported named symbols actually exported.
    for path, original in list(repaired.items()):
        if not path.endswith(('.js', '.jsx', '.ts', '.tsx')):
            continue
        code = _ensure_missing_named_exports(path, original, repaired, logs)
        if code != original:
            repaired[path] = code
            logs.append(f'Deterministic consistency repair updated {path}')
    return repaired, logs
