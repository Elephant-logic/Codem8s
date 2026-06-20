from __future__ import annotations

import json
import time
from pathlib import Path

from .models import BuildState
from .project_store import store_dir


def snapshots_dir(project_id: str) -> Path:
    safe = ''.join(ch for ch in project_id if ch.isalnum() or ch in '-_')
    path = store_dir() / safe / 'snapshots'
    path.mkdir(parents=True, exist_ok=True)
    return path


def dump_state(state: BuildState) -> dict:
    if hasattr(state, 'model_dump'):
        return state.model_dump(mode='json')
    return json.loads(state.json())


def load_state(data: dict) -> BuildState:
    if hasattr(BuildState, 'model_validate'):
        return BuildState.model_validate(data)
    return BuildState.parse_obj(data)


def create_snapshot(state: BuildState, label: str = 'manual') -> dict:
    folder = snapshots_dir(state.project_id)
    existing = sorted(folder.glob('snapshot_*.json'))
    number = len(existing) + 1
    snapshot_id = f'snapshot_{number:03d}'
    payload = {
        'snapshot_id': snapshot_id,
        'label': label,
        'created_at': time.time(),
        'status': state.status,
        'file_count': len(state.files),
        'valid_count': sum(1 for item in state.files.values() if item.status == 'valid'),
        'state': dump_state(state),
    }
    (folder / f'{snapshot_id}.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return {k: payload[k] for k in ['snapshot_id', 'label', 'created_at', 'status', 'file_count', 'valid_count']}


def list_snapshots(project_id: str) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(snapshots_dir(project_id).glob('snapshot_*.json')):
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
            rows.append({k: payload.get(k) for k in ['snapshot_id', 'label', 'created_at', 'status', 'file_count', 'valid_count']})
        except Exception:
            continue
    return rows


def restore_snapshot(project_id: str, snapshot_id: str) -> BuildState | None:
    safe_id = ''.join(ch for ch in snapshot_id if ch.isalnum() or ch in '-_')
    path = snapshots_dir(project_id) / f'{safe_id}.json'
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
        state = load_state(payload['state'])
        state.logs.append(f'Restored {safe_id}')
        return state
    except Exception:
        return None
