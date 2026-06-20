from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

STORE_DIR = Path('/opt/render/.codem8s/agent_memory')
FALLBACK_DIR = Path('/tmp/codem8s_agent_memory')


class MemoryRecord(BaseModel):
    memory_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str | None = None
    project_id: str | None = None
    category: str = 'general'
    pattern: str
    symptom: str = ''
    fix: str = ''
    lesson: str = ''
    tags: list[str] = Field(default_factory=list)
    success: bool | None = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    use_count: int = 0


class MemoryCreateRequest(BaseModel):
    agent_id: str | None = None
    project_id: str | None = None
    category: str = 'general'
    pattern: str
    symptom: str = ''
    fix: str = ''
    lesson: str = ''
    tags: list[str] = Field(default_factory=list)
    success: bool | None = None


def memory_dir() -> Path:
    try:
        STORE_DIR.mkdir(parents=True, exist_ok=True)
        test = STORE_DIR / '.write_test'
        test.write_text('ok', encoding='utf-8')
        test.unlink(missing_ok=True)
        return STORE_DIR
    except Exception:
        FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
        return FALLBACK_DIR


def _dump(record: MemoryRecord) -> dict[str, Any]:
    if hasattr(record, 'model_dump'):
        return record.model_dump(mode='json')
    return json.loads(record.json())


def _load(path: Path) -> MemoryRecord | None:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if hasattr(MemoryRecord, 'model_validate'):
            return MemoryRecord.model_validate(data)
        return MemoryRecord.parse_obj(data)
    except Exception:
        return None


def save_memory(record: MemoryRecord) -> MemoryRecord:
    record.updated_at = time.time()
    safe = ''.join(ch for ch in record.memory_id if ch.isalnum() or ch in '-_')
    (memory_dir() / f'{safe}.json').write_text(json.dumps(_dump(record), indent=2), encoding='utf-8')
    return record


def create_memory(req: MemoryCreateRequest) -> MemoryRecord:
    existing = find_similar_memory(req.pattern, req.tags)
    if existing:
        if req.lesson and req.lesson not in existing.lesson:
            existing.lesson = (existing.lesson + '\n' + req.lesson).strip()
        if req.fix and req.fix not in existing.fix:
            existing.fix = (existing.fix + '\n' + req.fix).strip()
        existing.tags = sorted(set(existing.tags + req.tags))
        if req.success is not None:
            existing.success = req.success
        return save_memory(existing)
    return save_memory(MemoryRecord(**req.model_dump() if hasattr(req, 'model_dump') else req.dict()))


def list_memory(category: str | None = None, tag: str | None = None, limit: int = 100) -> list[MemoryRecord]:
    records: list[MemoryRecord] = []
    for path in memory_dir().glob('*.json'):
        record = _load(path)
        if not record:
            continue
        if category and record.category != category:
            continue
        if tag and tag not in record.tags:
            continue
        records.append(record)
    records.sort(key=lambda item: (item.success is not True, -item.use_count, -item.updated_at))
    return records[:max(1, min(limit, 500))]


def find_similar_memory(pattern: str, tags: list[str] | None = None) -> MemoryRecord | None:
    needle = pattern.lower().strip()
    tagset = set(tags or [])
    best: MemoryRecord | None = None
    best_score = 0
    for record in list_memory(limit=500):
        score = 0
        hay = ' '.join([record.pattern, record.symptom, record.fix, record.lesson, *record.tags]).lower()
        if needle and needle in hay:
            score += 5
        for part in needle.split():
            if len(part) > 3 and part in hay:
                score += 1
        score += len(tagset.intersection(record.tags)) * 2
        if score > best_score:
            best = record
            best_score = score
    return best if best_score >= 4 else None


def search_memory(query: str, limit: int = 12) -> list[MemoryRecord]:
    query_low = query.lower()
    scored: list[tuple[int, MemoryRecord]] = []
    for record in list_memory(limit=500):
        hay = ' '.join([record.category, record.pattern, record.symptom, record.fix, record.lesson, *record.tags]).lower()
        score = 0
        for token in query_low.split():
            if len(token) > 2 and token in hay:
                score += 1
        if query_low in hay:
            score += 6
        if score:
            scored.append((score, record))
    scored.sort(key=lambda item: (-item[0], item[1].success is not True, -item[1].use_count))
    results = [record for _, record in scored[:max(1, min(limit, 50))]]
    for record in results:
        record.use_count += 1
        save_memory(record)
    return results


def seed_core_memories() -> None:
    if any(memory_dir().glob('*.json')):
        return
    seeds = [
        MemoryCreateRequest(category='build_failure', pattern='vite default export mismatch', symptom='default is not exported by module', fix='Align import style and export style across every connected file. If App imports default, component must export default. If importing named, target must export named.', tags=['vite', 'react', 'imports', 'exports'], success=True),
        MemoryCreateRequest(category='build_failure', pattern='missing local css import', symptom='Could not resolve ./Modal.css or other relative CSS import', fix='Remove the CSS import or generate the missing CSS file and add it to locked manifest before validation.', tags=['vite', 'css', 'missing-file'], success=True),
        MemoryCreateRequest(category='build_failure', pattern='commonjs require in vite esm app', symptom='require is not defined or module fails during Vite build', fix='Use ES module imports and exports in frontend files. Do not generate require() in Vite React apps.', tags=['vite', 'esm', 'require'], success=True),
        MemoryCreateRequest(category='product_quality', pattern='shallow dashboard', symptom='Dashboard only shows generic cards or record counts', fix='Generate KPI cards, activity feed, status breakdown, priority list, trends, search/filter controls, and realistic data-backed sections.', tags=['dashboard', 'ui', 'quality'], success=True),
        MemoryCreateRequest(category='data_model', pattern='appPlan sampleData mismatch', symptom='App references fields that do not exist in APP_PLAN or sampleData', fix='Choose one coherent data contract. APP_PLAN should describe navigation/config; sampleData should hold records; UI should derive metrics from sampleData.', tags=['data', 'contract', 'react'], success=True),
    ]
    for seed in seeds:
        create_memory(seed)


seed_core_memories()
