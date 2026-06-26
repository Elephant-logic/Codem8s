import React, { useMemo, useState } from 'react';

const API = import.meta.env.VITE_API_BASE_URL || 'https://codem8s-docker.onrender.com';
const QUALITY_TARGET = 72;
const IMPORT_RE = /import(?:\s+[^'\"]+\s+from)?\s*['\"]([^'\"]+)['\"]|from\s+['\"]([^'\"]+)['\"]/g;
const EXPORT_RE = /\bexport\s+(?:default\s+)?(?:function|class|const|let|var|type|interface)\s+([A-Za-z_$][\w$]*)|\bexport\s*\{([^}]+)\}/g;
const TEXT_EXTENSIONS = ['.js', '.jsx', '.ts', '.tsx', '.css', '.html', '.json', '.md', '.py', '.txt', '.yml', '.yaml'];

function isTextFile(path) {
  return TEXT_EXTENSIONS.some((ext) => path.endsWith(ext)) || ['package.json', 'requirements.txt', 'Dockerfile', 'Makefile'].includes(path.split('/').pop());
}

function normalise(parts) {
  const out = [];
  parts.forEach((part) => {
    if (!part || part === '.') return;
    if (part === '..') out.pop();
    else out.push(part);
  });
  return out.join('/');
}

function resolveRelative(fromPath, spec, filesByPath) {
  if (!spec.startsWith('.')) return null;
  const base = fromPath.split('/').slice(0, -1);
  const raw = normalise([...base, ...spec.split('/')]);
  const candidates = [raw, `${raw}.js`, `${raw}.jsx`, `${raw}.ts`, `${raw}.tsx`, `${raw}.json`, `${raw}.css`, `${raw}/index.js`, `${raw}/index.jsx`, `${raw}/index.ts`, `${raw}/index.tsx`];
  return candidates.find((candidate) => filesByPath[candidate]) || null;
}

function importsFor(path, content) {
  const specs = [];
  if (!/\.(js|jsx|ts|tsx)$/.test(path)) return specs;
  IMPORT_RE.lastIndex = 0;
  let match;
  while ((match = IMPORT_RE.exec(content))) specs.push(match[1] || match[2]);
  return [...new Set(specs.filter(Boolean))].sort();
}

function exportsFor(path, content) {
  const exports = new Set();
  if (!/\.(js|jsx|ts|tsx)$/.test(path)) return [];
  EXPORT_RE.lastIndex = 0;
  let match;
  while ((match = EXPORT_RE.exec(content))) {
    if (match[1]) exports.add(match[1]);
    if (match[2]) match[2].split(',').forEach((raw) => { const name = raw.trim().split(' as ').pop().replace(/[^A-Za-z0-9_$].*$/, ''); if (name) exports.add(name); });
  }
  if (/\bexport\s+default\b/.test(content)) exports.add('default');
  return [...exports].sort();
}

function roleFor(path, content = '') {
  const name = path.split('/').pop().toLowerCase();
  const low = content.slice(0, 4000).toLowerCase();
  if (name === 'package.json') return 'package manifest and dependency/script contract';
  if (/App\.(jsx|tsx)$/.test(path)) return 'main React app shell that composes the top-level UI';
  if (/(main|index)\.(jsx|tsx)$/.test(path)) return 'frontend entry point that mounts the app';
  if (low.includes('fastapi') || name === 'main.py') return 'backend/API entry point or service module';
  if (low.includes('canvas') || low.includes('requestanimationframe')) return 'canvas/game rendering or animation module';
  if (low.includes('zustand') || low.includes('reducer') || path.toLowerCase().includes('store')) return 'state management module';
  if (/\.(jsx|tsx)$/.test(path)) return 'React UI component or screen';
  if (/\.(js|ts)$/.test(path)) return 'JavaScript/TypeScript utility, data, or app module';
  if (/\.css$/.test(path)) return 'stylesheet/design system';
  if (/\.py$/.test(path)) return 'Python module';
  return 'project file';
}

function buildTopology(fileMap) {
  const topology = {};
  Object.entries(fileMap).forEach(([path, content]) => {
    const specs = importsFor(path, content);
    const imports = specs.map((spec) => resolveRelative(path, spec, fileMap)).filter(Boolean);
    topology[path] = { path, role: roleFor(path, content), import_specs: specs, imports, exports: exportsFor(path, content), dependents: [], lines: content.split('\n').length, size: content.length };
  });
  Object.values(topology).forEach((meta) => meta.imports.forEach((target) => topology[target]?.dependents.push(meta.path)));
  Object.values(topology).forEach((meta) => { meta.dependents = [...new Set(meta.dependents)].sort(); });
  return topology;
}

function explain(meta) {
  if (!meta) return 'Select a file to inspect it.';
  const exports = meta.exports.length ? meta.exports.slice(0, 8).join(', ') : 'no obvious exports';
  return `${meta.role}. It imports ${meta.imports.length} local file(s), is used by ${meta.dependents.length} local file(s), and exposes ${exports}.`;
}

export default function App() {
  const [idea, setIdea] = useState('Build a React/Vite tower defense game with waves, enemies, towers, upgrades, HUD, canvas gameplay, specialist game architecture, and polished UI.');
  const [instruction, setInstruction] = useState('Use dependency topology and real npm build logs to repair the app until it runs.');
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [sandbox, setSandbox] = useState(null);
  const [sandboxLogs, setSandboxLogs] = useState([]);
  const [quality, setQuality] = useState(null);
  const [memory, setMemory] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [localFiles, setLocalFiles] = useState({});
  const [selectedPath, setSelectedPath] = useState('');
  const [editedContent, setEditedContent] = useState('');
  const [workbenchNotice, setWorkbenchNotice] = useState('');

  const projectId = state?.project_id;
  const files = Object.values(state?.files || {});
  const topology = useMemo(() => buildTopology(localFiles), [localFiles]);
  const selectedMeta = selectedPath ? topology[selectedPath] : null;
  const buildPassed = Boolean(sandbox?.build_ok);
  const qualityNeedsWork = buildPassed && quality && quality.total < QUALITY_TARGET;
  const displayStatus = buildPassed ? (qualityNeedsWork ? 'build passed / quality needs improvement' : 'build passed') : (state?.status || 'no project');
  const progress = useMemo(() => ({ total: files.length, valid: files.filter((f) => f.status === 'valid').length, generated: files.filter((f) => f.content).length, rejected: files.filter((f) => f.status === 'rejected').length }), [files]);

  async function request(path, options = {}) {
    const res = await fetch(API + path, options);
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch {}
    if (!res.ok) throw new Error(data?.detail || text || `Request failed ${res.status}`);
    return data;
  }

  function post(path, body) { return request(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined }); }
  async function run(label, fn) { setBusy(true); setNotice(label); try { await fn(); } catch (err) { setNotice(`Failed: ${String(err.message || err)}`); } finally { setBusy(false); } }
  async function refresh(id = projectId) { if (!id) return; await Promise.allSettled([request(`/projects/${id}/quality`).then(setQuality), request(`/agent-memory?limit=20`).then((d) => setMemory(d.memory || [])), request(`/projects/${id}/timeline`).then((d) => setTimeline(d.events || [])), refreshSandbox(id)]); }
  async function refreshSandbox(id = projectId) { if (!id) return; const logs = await request(`/projects/${id}/sandbox/logs?limit=300`); setSandboxLogs(logs.logs || []); setSandbox(await request(`/projects/${id}/sandbox/status`)); }
  async function runSandbox(id = projectId) { if (!id) return null; setNotice('Running live Docker sandbox: npm install then npm run build...'); const result = await post(`/projects/${id}/sandbox/start`); setSandbox(result); await refreshSandbox(id); setNotice(result.build_ok ? 'Build passed. Preview ready.' : 'Build failed. Use AI Fix + Re-run or Work Through Errors.'); return result; }
  async function createProject() { await run('Creating plan...', async () => { const created = await post('/projects', { idea, use_ai: true }); setState(created); setSandbox(null); setSandboxLogs([]); await refresh(created.project_id); setNotice('Plan created. Press Approve + Build + Sandbox.'); }); }
  async function buildNext() { if (!projectId) return; await run('Building next file...', async () => { const next = await post(`/projects/${projectId}/build-next`); setState(next); await refresh(next.project_id); }); }
  async function buildAllSandbox() { if (!projectId) return; await run('Generating files, repairing, then running live build...', async () => { const built = await post(`/projects/${projectId}/build-all`); setState(built); await refresh(built.project_id); await runSandbox(built.project_id); }); }
  async function validateSandbox() { if (!projectId) return; await run('Validating, repairing, then running live build...', async () => { const validated = await post(`/projects/${projectId}/validate`); setState(validated); await refresh(validated.project_id); await runSandbox(validated.project_id); }); }
  async function agentTeamSandbox() { if (!projectId) return; await run('Running agents, then live build...', async () => { const result = await post(`/projects/${projectId}/team/run`, { goal: instruction, max_cycles: 1 }); if (result.project) setState(result.project); await refresh(result.project?.project_id || projectId); await runSandbox(result.project?.project_id || projectId); }); }
  async function aiFix() { if (!projectId) return; await run('AI fixing from build logs...', async () => { const result = await post(`/projects/${projectId}/sandbox/fix`, { instruction }); setSandbox(result); await refresh(projectId); }); }
  async function improveQuality() { if (!projectId) return; const issues = quality?.issues?.join('; ') || 'Improve product depth, sample data, design system, workflows, and real app states.'; const qualityInstruction = `Improve product quality without breaking the passing build. Current quality score is ${quality?.total || 0}/100. Fix these issues: ${issues}.`; await run('Improving quality, then rebuilding sandbox...', async () => { const changed = await post(`/projects/${projectId}/change`, { instruction: qualityInstruction }); setState(changed); const result = await post(`/projects/${projectId}/team/run`, { goal: qualityInstruction, max_cycles: 1 }); if (result.project) setState(result.project); const id = result.project?.project_id || changed.project_id; await refresh(id); await runSandbox(id); }); }
  async function workErrors() { if (!projectId) return; await run('Working through build errors...', async () => { let result = await runSandbox(projectId); for (let round = 1; round <= 8; round += 1) { if (result?.build_ok) break; setNotice(`Repair round ${round}...`); result = await post(`/projects/${projectId}/sandbox/fix`, { instruction }); setSandbox(result); await refreshSandbox(projectId); } await refresh(projectId); }); }
  async function applyInstruction() { if (!projectId) return; await run('Applying instruction...', async () => { const changed = await post(`/projects/${projectId}/change`, { instruction }); setState(changed); await refresh(changed.project_id); }); }
  function openPreview() { if (sandbox?.preview_url) window.open(API + sandbox.preview_url, '_blank', 'noopener,noreferrer'); }
  function exportZip() { if (projectId) window.location = `${API}/projects/${projectId}/export-snapshot`; }

  async function loadFolder(event) {
    const selected = Array.from(event.target.files || []).filter((file) => isTextFile(file.webkitRelativePath || file.name));
    const entries = await Promise.all(selected.slice(0, 300).map(async (file) => [file.webkitRelativePath || file.name, await file.text()]));
    const map = Object.fromEntries(entries.map(([path, content]) => [path.split('/').slice(1).join('/') || path, content]));
    setLocalFiles(map);
    const first = Object.keys(map).sort()[0] || '';
    setSelectedPath(first);
    setEditedContent(map[first] || '');
    setWorkbenchNotice(`Loaded ${Object.keys(map).length} text/source files locally.`);
  }

  function selectWorkbenchFile(path) { setSelectedPath(path); setEditedContent(localFiles[path] || ''); }
  function saveWorkbenchFile() { if (!selectedPath) return; setLocalFiles((old) => ({ ...old, [selectedPath]: editedContent })); setWorkbenchNotice(`Updated local copy of ${selectedPath}.`); }
  function simpleRefactor() {
    if (!selectedPath) return;
    const cleaned = editedContent.replace(/[ \t]+$/gm, '').replace(/\n{4,}/g, '\n\n\n');
    setEditedContent(cleaned);
    setWorkbenchNotice('Applied safe whitespace cleanup. Deeper AI refactors can use the selected file context next.');
  }

  return (
    <main className="app">
      <h1>Codem8s Full Stack</h1>
      <p>Generate → repair → real npm build → sandbox preview → quality improve → export — plus existing project workbench.</p>
      <p><b>Backend:</b> {API}</p>
      {notice && <section className="card running"><b>{notice}</b>{busy && <div className="spinner" />}</section>}

      <section className="card">
        <h2>Existing Project Workbench</h2>
        <p>Load a folder, inspect file roles, see local imports/dependents/exports, edit safely, and plan refactors with topology context.</p>
        <input type="file" webkitdirectory="true" directory="true" multiple onChange={loadFolder} />
        {workbenchNotice && <p><b>{workbenchNotice}</b></p>}
        <div className="grid workbench-grid">
          <aside className="file-tree">
            <h3>Files / Topology</h3>
            {Object.keys(localFiles).sort().map((path) => <button className={path === selectedPath ? 'active file-button' : 'file-button'} key={path} onClick={() => selectWorkbenchFile(path)}>{path}</button>)}
          </aside>
          <section>
            <h3>{selectedPath || 'No file selected'}</h3>
            <p>{explain(selectedMeta)}</p>
            {selectedMeta && <div className="status-pills"><span className="pill">{selectedMeta.lines} lines</span><span className="pill">imports {selectedMeta.imports.length}</span><span className="pill">used by {selectedMeta.dependents.length}</span><span className="pill">exports {selectedMeta.exports.length}</span></div>}
            {selectedMeta?.risks?.map((risk) => <p className="warn" key={risk}>• {risk}</p>)}
            <div className="grid"><pre className="log"><b>Imports</b>\n{selectedMeta?.imports?.join('\n') || 'None'}</pre><pre className="log"><b>Dependents</b>\n{selectedMeta?.dependents?.join('\n') || 'None'}</pre><pre className="log"><b>Exports</b>\n{selectedMeta?.exports?.join('\n') || 'None'}</pre></div>
            <textarea className="code-editor" value={editedContent} onChange={(e) => setEditedContent(e.target.value)} />
            <div className="row action-row"><button onClick={saveWorkbenchFile} disabled={!selectedPath}>Save Local Edit</button><button onClick={simpleRefactor} disabled={!selectedPath}>Safe Cleanup Refactor</button></div>
          </section>
        </div>
      </section>

      <div className="grid">
        <section className="card">
          <h2>Idea</h2>
          <textarea value={idea} onChange={(e) => setIdea(e.target.value)} />
          <div className="row action-row"><button onClick={createProject} disabled={busy}>Create / Review Plan</button><button onClick={buildNext} disabled={!projectId || busy}>Build Next</button><button onClick={buildAllSandbox} disabled={!projectId || busy}>Approve + Build + Sandbox</button><button onClick={validateSandbox} disabled={!projectId || busy}>Validate / Repair + Sandbox</button><button onClick={agentTeamSandbox} disabled={!projectId || busy}>Run Agents + Sandbox</button><button onClick={() => runSandbox()} disabled={!projectId || busy}>Run Sandbox Build</button><button onClick={improveQuality} disabled={!projectId || busy}>Improve Quality + Rebuild</button><button onClick={aiFix} disabled={!projectId || busy}>AI Fix + Re-run</button><button onClick={workErrors} disabled={!projectId || busy}>Work Through Errors</button><button onClick={exportZip} disabled={!projectId}>Export Snapshot</button></div>
          {state && <p><b>Status:</b> {displayStatus} | <b>Progress:</b> {progress.valid}/{progress.total} valid | <b>Generated:</b> {progress.generated} | <b>Rejected:</b> {progress.rejected}</p>}
          {qualityNeedsWork && <p className="warn">Build is green. Quality is below target. Press Improve Quality + Rebuild.</p>}
          <h2>Steer While Building</h2><textarea value={instruction} onChange={(e) => setInstruction(e.target.value)} /><button onClick={applyInstruction} disabled={!projectId || busy}>Apply Instruction</button>
        </section>
        <section className="card"><h2>Spec</h2><pre className="log">{state ? JSON.stringify(state.spec, null, 2) : 'No project yet'}</pre></section>
      </div>
      <section className="card sandbox-card"><h2>Live Sandbox</h2><div className="status-pills"><span className={sandbox?.running ? 'pill ok-bg' : 'pill'}>{sandbox?.running ? 'Running' : 'Stopped'}</span><span className={sandbox?.build_ok ? 'pill ok-bg' : 'pill bad-bg'}>{sandbox?.build_ok ? 'Build OK' : 'Build not green'}</span></div><div className="row"><button onClick={() => refreshSandbox()} disabled={!projectId}>Refresh Logs</button><button onClick={openPreview} disabled={!sandbox?.preview_url}>Open Preview</button></div>{sandbox && <p><b>Preview:</b> {sandbox.preview_url || 'not started'}<br /><b>Root:</b> {sandbox.root || 'not created'}</p>}{sandbox?.last_error && <pre className="log bad-box">{sandbox.last_error}</pre>}<pre className="log sandbox-log">{sandboxLogs.length ? sandboxLogs.join('\n') : 'No sandbox logs yet'}</pre></section>
      <section className="card quality-card"><h2>Product Quality Score</h2>{quality ? <><div className="quality-score"><strong>{quality.total}/100</strong></div>{quality.issues?.map((issue) => <p className="bad" key={issue}>• {issue}</p>)}</> : <p>No quality score yet.</p>}</section>
      <section className="card memory-card"><h2>Agent Memory Viewer</h2>{memory.map((item) => <article className="memory-item" key={item.memory_id}><b>{item.pattern}</b><p>{item.fix || item.lesson || item.symptom}</p></article>)}</section>
      <section className="card timeline-card"><h2>Timeline</h2>{timeline.slice().reverse().map((event, index) => <div className={`timeline-item ${event.kind}`} key={`${index}-${event.detail}`}><b>{event.title}</b><span>{event.detail}</span></div>)}</section>
      <section className="card"><h2>Files</h2>{files.map((file) => <div className="file" key={file.path}><b>{file.path}</b> <span className={file.status === 'valid' ? 'ok' : 'bad'}>{file.status}</span>{file.content && <pre className="log">{file.content.slice(0, 900)}</pre>}{file.errors?.length > 0 && <pre className="bad">{file.errors.join('\n')}</pre>}</div>)}</section>
      <section className="card"><h2>Logs</h2><pre className="log">{state?.logs?.join('\n') || ''}</pre></section>
    </main>
  );
}
