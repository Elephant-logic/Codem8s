from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import PurePosixPath
from uuid import uuid4

from .agent_llm import chat_json
from .models import BuildState, FileSpec, ProjectSpec

TEXT_EXTENSIONS = {'.js', '.jsx', '.ts', '.tsx', '.css', '.html', '.json', '.md', '.py', '.txt', '.yml', '.yaml'}
MAX_FILE_BYTES = 350_000
MAX_IMPORT_BYTES = 4_000_000

IMPORT_RE = re.compile(r"import(?:\s+[^'\"]+\s+from)?\s*['\"]([^'\"]+)['\"]|from\s+['\"]([^'\"]+)['\"]")
EXPORT_RE = re.compile(r"\bexport\s+(?:default\s+)?(?:function|class|const|let|var|type|interface)\s+([A-Za-z_$][\w$]*)|\bexport\s*\{([^}]+)\}")
PY_IMPORT_RE = re.compile(r"^\s*(?:from\s+([A-Za-z0-9_\.]+)\s+import|import\s+([A-Za-z0-9_\.]+))", re.M)
PY_SYMBOL_RE = re.compile(r"^\s*(?:def|class)\s+([A-Za-z_][\w]*)", re.M)


def safe_zip_path(name: str) -> str | None:
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or name.endswith('/'):
        return None
    parts = [p for p in path.parts if p not in {'', '.'}]
    if not parts:
        return None
    if len(parts) > 1 and parts[0] not in {'frontend', 'backend', 'src', 'app', 'public'} and '.' not in parts[0]:
        parts = parts[1:]
    clean = '/'.join(parts)
    if not clean or clean.startswith('.') or '/.' in clean:
        return None
    return clean


def is_text_path(path: str) -> bool:
    suffix = PurePosixPath(path).suffix.lower()
    return suffix in TEXT_EXTENSIONS or PurePosixPath(path).name in {'Dockerfile', 'Makefile', 'requirements.txt'}


def import_zip_project(zip_bytes: bytes, name: str = 'Uploaded project') -> BuildState:
    if len(zip_bytes) > MAX_IMPORT_BYTES:
        raise ValueError('Project zip is too large for this importer. Try a smaller source-only zip.')
    files: dict[str, FileSpec] = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        for info in archive.infolist():
            path = safe_zip_path(info.filename)
            if not path or not is_text_path(path) or info.file_size > MAX_FILE_BYTES:
                continue
            try:
                content = archive.read(info).decode('utf-8')
            except UnicodeDecodeError:
                content = archive.read(info).decode('utf-8', errors='replace')
            files[path] = FileSpec(path=path, purpose=describe_path_role(path, content), status='valid', content=content)
    if not files:
        raise ValueError('No readable source files were found in the uploaded zip.')
    topology = build_topology({p: f.content for p, f in files.items()})
    spec = ProjectSpec(
        app_name=name.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ') or 'Imported Project',
        goal='Imported existing codebase for topology-aware inspection, refactoring, build repair, and explanation.',
        stack=detect_stack(files),
        features=['Existing project import', 'File topology', 'File inspection', 'Dependency-aware refactor'],
        files={p: f.purpose for p, f in files.items()},
        change_log=['IMPORTED_ZIP', 'TOPOLOGY_JSON:' + json.dumps(topology, separators=(',', ':'))],
    )
    return BuildState(project_id=str(uuid4()), use_ai=True, spec=spec, files=files, logs=[f'Imported {len(files)} source files from {name}', 'Topology built from source imports'], status='complete')


def detect_stack(files: dict[str, FileSpec]) -> str:
    package = files.get('package.json') or files.get('frontend/package.json')
    if package:
        try:
            data = json.loads(package.content)
            deps = ' '.join([*data.get('dependencies', {}).keys(), *data.get('devDependencies', {}).keys()])
            if 'vite' in deps and 'react' in deps:
                return 'react-vite'
            if 'next' in deps:
                return 'nextjs'
            if 'react' in deps:
                return 'react'
        except Exception:
            pass
    if any(p.endswith('.py') for p in files):
        return 'python-or-mixed'
    return 'imported-codebase'


def describe_path_role(path: str, content: str) -> str:
    name = PurePosixPath(path).name.lower()
    low = content[:4000].lower()
    if name == 'package.json':
        return 'JavaScript package manifest and scripts/dependency contract'
    if path.endswith(('App.jsx', 'App.tsx')):
        return 'Main React application shell that composes screens, providers, and top-level UI'
    if path.endswith(('main.jsx', 'main.tsx', 'index.jsx', 'index.tsx')):
        return 'Frontend entry point that mounts the app into the browser'
    if 'fastapi' in low or name == 'main.py':
        return 'Backend/API entry point or service module'
    if 'canvas' in low or 'requestanimationframe' in low:
        return 'Canvas/game rendering or animation module'
    if 'zustand' in low or 'reducer' in low or 'store' in path.lower():
        return 'State management module'
    if path.endswith(('.css', '.scss')):
        return 'Stylesheet/design system'
    if path.endswith(('.jsx', '.tsx')):
        return 'React UI component or screen'
    if path.endswith(('.js', '.ts')):
        return 'JavaScript/TypeScript utility, data, or application module'
    if path.endswith('.py'):
        return 'Python module'
    return 'Imported project file'


def normalise(path: PurePosixPath) -> str:
    parts: list[str] = []
    for part in path.parts:
        if part in {'', '.'}:
            continue
        if part == '..':
            if parts:
                parts.pop()
        else:
            parts.append(part)
    return '/'.join(parts)


def resolve_relative(path: str, spec: str, files: dict[str, str]) -> str | None:
    if not spec.startswith('.'):
        return None
    raw = normalise(PurePosixPath(path).parent / spec)
    candidates = [raw, raw + '.js', raw + '.jsx', raw + '.ts', raw + '.tsx', raw + '.json', raw + '.css', raw + '/index.js', raw + '/index.jsx', raw + '/index.ts', raw + '/index.tsx']
    for candidate in candidates:
        if candidate in files:
            return candidate
    return None


def extract_import_specs(path: str, content: str) -> list[str]:
    specs: list[str] = []
    if path.endswith(('.js', '.jsx', '.ts', '.tsx')):
        for match in IMPORT_RE.finditer(content):
            spec = match.group(1) or match.group(2)
            if spec:
                specs.append(spec)
    elif path.endswith('.py'):
        for match in PY_IMPORT_RE.finditer(content):
            spec = match.group(1) or match.group(2)
            if spec:
                specs.append(spec)
    return sorted(set(specs))


def extract_exports(path: str, content: str) -> list[str]:
    exports: set[str] = set()
    if path.endswith(('.js', '.jsx', '.ts', '.tsx')):
        for match in EXPORT_RE.finditer(content):
            if match.group(1):
                exports.add(match.group(1))
            if match.group(2):
                for raw in match.group(2).split(','):
                    token = raw.strip().split(' as ')[-1].strip()
                    token = re.sub(r'[^A-Za-z0-9_$].*$', '', token)
                    if token:
                        exports.add(token)
        if re.search(r'\bexport\s+default\b', content):
            exports.add('default')
    elif path.endswith('.py'):
        exports.update(PY_SYMBOL_RE.findall(content))
    return sorted(exports)


def build_topology(files: dict[str, str]) -> dict[str, dict]:
    topology: dict[str, dict] = {}
    for path, content in files.items():
        specs = extract_import_specs(path, content)
        imports = [resolved for resolved in (resolve_relative(path, spec, files) for spec in specs) if resolved]
        topology[path] = {
            'role': describe_path_role(path, content),
            'import_specs': specs,
            'imports': imports,
            'exports': extract_exports(path, content),
            'dependents': [],
            'lines': len(content.splitlines()),
            'size': len(content),
        }
    for path, meta in topology.items():
        for imported in meta.get('imports', []):
            if imported in topology:
                topology[imported]['dependents'].append(path)
    for meta in topology.values():
        meta['dependents'] = sorted(set(meta.get('dependents', [])))
    return topology


def inspect_file(files: dict[str, str], path: str) -> dict:
    if path not in files:
        raise KeyError(path)
    topology = build_topology(files)
    meta = topology.get(path, {})
    risks = []
    if meta.get('lines', 0) > 350:
        risks.append('Large file: consider splitting responsibilities.')
    if not meta.get('exports') and path.endswith(('.js', '.jsx', '.ts', '.tsx', '.py')):
        risks.append('No obvious exports found; this may be entry-only or hard to reuse/test.')
    if len(meta.get('dependents', [])) > 5:
        risks.append('High fan-in: changes here can affect many files.')
    if len(meta.get('imports', [])) > 8:
        risks.append('High fan-out: this file depends on many neighbours.')
    exports = ', '.join(meta.get('exports', [])[:8]) or 'no obvious exports'
    summary = f"{describe_path_role(path, files[path])}. It imports {len(meta.get('imports', []))} local file(s), is used by {len(meta.get('dependents', []))} local file(s), and exposes {exports}."
    return {'path': path, 'purpose': describe_path_role(path, files[path]), 'imports': meta.get('imports', []), 'import_specs': meta.get('import_specs', []), 'dependents': meta.get('dependents', []), 'exports': meta.get('exports', []), 'lines': meta.get('lines', 0), 'size': meta.get('size', 0), 'risks': risks, 'summary': summary}


def refactor_file_with_ai(files: dict[str, str], path: str, instruction: str) -> str:
    if path not in files:
        raise KeyError(path)
    topology = build_topology(files)
    meta = topology.get(path, {})
    connected = [path, *meta.get('imports', [])[:8], *meta.get('dependents', [])[:8]]
    payload = {'target_path': path, 'instruction': instruction, 'target_file': files[path][:18000], 'target_meta': meta, 'connected_files': {p: files[p][:5000] for p in connected if p in files and p != path}}
    system = '''You are Codem8s Existing Project Workbench.
Return JSON only: {"content":"full replacement target file contents", "notes":["brief note"]}
Refactor or fix only the target file unless the instruction explicitly asks for a wider change.
Preserve public exports used by dependents unless the instruction explicitly asks to change them.
Do not return markdown fences, placeholders, TODOs, or partial snippets.'''
    data = chat_json(system, json.dumps(payload, indent=2), temperature=0.08)
    if data and isinstance(data.get('content'), str):
        return str(data['content']).strip() + '\n'
    raise RuntimeError('AI refactor did not return replacement content')
