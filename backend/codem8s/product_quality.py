from __future__ import annotations

import re
from dataclasses import dataclass, asdict


@dataclass
class QualityScore:
    product_architecture: int
    ui_depth: int
    workflow_depth: int
    data_richness: int
    design_system: int
    total: int
    issues: list[str]
    suggestions: list[str]


def _count_terms(text: str, terms: list[str]) -> int:
    low = text.lower()
    return sum(1 for term in terms if term.lower() in low)


def _all_frontend(files: dict[str, str]) -> str:
    return '\n'.join(content for path, content in files.items() if path.startswith('frontend/') and path.endswith(('.js', '.jsx', '.css')))


def score_product_quality(files: dict[str, str]) -> QualityScore:
    issues: list[str] = []
    suggestions: list[str] = []
    app = files.get('frontend/src/App.jsx', '')
    dashboard = files.get('frontend/src/components/Dashboard.jsx', '')
    sample = files.get('frontend/src/data/sampleData.js', '')
    styles = files.get('frontend/src/styles.css', '')
    all_frontend = _all_frontend(files)

    architecture_terms = ['persona', 'workflow', 'permission', 'role', 'audit', 'automation', 'notification', 'report', 'client', 'team', 'project', 'pipeline']
    ui_terms = ['dashboard', 'activity', 'search', 'filter', 'status', 'timeline', 'kanban', 'chart', 'table', 'modal', 'empty', 'loading', 'error', 'quick action']
    workflow_terms = ['onClick', 'useState', 'filter(', 'map(', 'set', 'create', 'update', 'delete', 'selected', 'active', 'tab', 'search']
    data_terms = ['projects', 'tasks', 'users', 'comments', 'activities', 'attachments', 'status', 'priority', 'dueDate', 'owner', 'team']
    design_terms = ['linear-gradient', 'grid', 'flex', 'box-shadow', 'border-radius', 'badge', 'sidebar', 'card', 'responsive', '@media', 'gap', 'transition']

    product_architecture = min(100, _count_terms(all_frontend, architecture_terms) * 9)
    ui_depth = min(100, _count_terms(all_frontend, ui_terms) * 7 + min(len(re.findall(r'<[A-Za-z]', app + dashboard)), 60))
    workflow_depth = min(100, _count_terms(all_frontend, workflow_terms) * 8)
    data_richness = min(100, _count_terms(sample + all_frontend, data_terms) * 7 + min(len(sample) // 80, 35))
    design_system = min(100, _count_terms(styles, design_terms) * 8 + min(len(styles) // 120, 25))

    if len(dashboard.strip()) < 1800:
        issues.append('Dashboard is too shallow')
        suggestions.append('Add KPI cards, status breakdown, activity feed, priority queue, charts, filters, and quick actions.')
        ui_depth = min(ui_depth, 55)
    if len(sample.strip()) < 2500:
        issues.append('Sample data is too thin')
        suggestions.append('Generate realistic connected records: projects, tasks, users, activity, comments, documents, and timelines.')
        data_richness = min(data_richness, 55)
    if len(styles.strip()) < 2500:
        issues.append('Design system is too basic')
        suggestions.append('Add a richer responsive design system with cards, badges, sidebars, grids, empty states, and interaction states.')
        design_system = min(design_system, 55)
    if _count_terms(all_frontend, ['empty', 'loading', 'error']) < 2:
        issues.append('Missing product states')
        suggestions.append('Add empty, loading, and error states to key screens.')
        ui_depth = min(ui_depth, 65)
    if _count_terms(all_frontend, ['search', 'filter']) < 2:
        issues.append('Missing search/filter workflows')
        suggestions.append('Add global search and per-screen filters backed by real sample data.')
        workflow_depth = min(workflow_depth, 65)

    total = round((product_architecture + ui_depth + workflow_depth + data_richness + design_system) / 5)
    return QualityScore(product_architecture, ui_depth, workflow_depth, data_richness, design_system, total, issues, suggestions)


def quality_as_dict(score: QualityScore) -> dict:
    return asdict(score)


def quality_repair_prompt(score: QualityScore) -> str:
    if not score.issues:
        return 'Product quality passed. Preserve quality while repairing build issues.'
    return (
        'Product quality failed. Improve the app as a real product, not a scaffold.\n'
        f'Scores: architecture={score.product_architecture}, ui={score.ui_depth}, workflow={score.workflow_depth}, data={score.data_richness}, design={score.design_system}, total={score.total}.\n'
        'Issues:\n- ' + '\n- '.join(score.issues) + '\n'
        'Required improvements:\n- ' + '\n- '.join(score.suggestions)
    )
