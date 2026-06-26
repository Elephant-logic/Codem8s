import React, { useEffect, useMemo, useState } from 'react';

const API = import.meta.env.VITE_API_BASE_URL || 'https://codem8s-docker.onrender.com';
const TEXT_EXTENSIONS = ['.js', '.jsx', '.ts', '.tsx', '.css', '.html', '.json', '.md', '.py', '.txt', '.yml', '.yaml'];
const WORKSPACE_KEY = 'codem8s-workspace-v1';

function isTextFile(path) { return TEXT_EXTENSIONS.some((ext) => path.endsWith(ext)) || ['package.json', 'requirements.txt', 'Dockerfile', 'Makefile'].includes(path.split('/').pop()); }
function listFiles(project) { return Object.values(project?.files || {}).sort((a, b) => a.path.localeCompare(b.path)); }
function wantsRun(text) { return /\b(run|preview|build|sandbox|show|test|make it work)\b/i.test(text || ''); }
function wantsWholeProject(text) { return /\b(all files|whole project|entire project|everywhere|across the project|multi[- ]file|app wide|global|app|site|ui|theme|layout)\b/i.test(text || ''); }
function readWorkspace() { try { return JSON.parse(localStorage.getItem(WORKSPACE_KEY) || '[]'); } catch { return []; } }
function writeWorkspace(items) { localStorage.setItem(WORKSPACE_KEY, JSON.stringify(items.slice(0, 20))); }
function normalise(parts) { const out = []; parts.forEach((part) => { if (!part || part === '.') return; if (part === '..') out.pop(); else out.push(part); }); return out.join('/'); }
function resolveRelative(fromPath, spec, fileMap) {
  if (!spec?.startsWith?.('.')) return null;
  const base = fromPath.split('/').slice(0, -1);
  const raw = normalise([...base, ...spec.split('/')]);
  const candidates = [raw, `${raw}.js`, `${raw}.jsx`, `${raw}.ts`, `${raw}.tsx`, `${raw}.json`, `${raw}.css`, `${raw}/index.js`, `${raw}/index.jsx`, `${raw}/index.ts`, `${raw}/index.tsx`];
  return candidates.find((candidate) => fileMap[candidate]) || null;
}
function importsFor(path, content) {
  if (!/\.(js|jsx|ts|tsx)$/.test(path)) return [];
  const specs = [];
  const re = /import(?:\s+[^'\"]+\s+from)?\s*['\"]([^'\"]+)['\"]|from\s+['\"]([^'\"]+)['\"]/g;
  let match;
  while ((match = re.exec(content || ''))) specs.push(match[1] || match[2]);
  return [...new Set(specs.filter(Boolean))].sort();
}
function buildProjectBrain(project) {
  const fileMap = Object.fromEntries(listFiles(project).map((f) => [f.path, f.content || '']));
  const files = Object.keys(fileMap);
  const imports = {}; const dependents = {};
  files.forEach((path) => { dependents[path] = []; });
  files.forEach((path) => { imports[path] = importsFor(path, fileMap[path]).map((spec) => resolveRelative(path, spec, fileMap)).filter(Boolean); imports[path].forEach((target) => dependents[target]?.push(path)); });
  const packageFile = project?.files?.['package.json'] || project?.files?.['frontend/package.json'];
  let scripts = []; let deps = [];
  try { const pkg = packageFile?.content ? JSON.parse(packageFile.content) : null; scripts = Object.keys(pkg?.scripts || {}); deps = Object.keys({ ...(pkg?.dependencies || {}), ...(pkg?.devDependencies || {}) }); } catch {}
  const htmlFiles = files.filter((p) => p.endsWith('.html'));
  const entryPoints = files.filter((p) => /(^|\/)(main|index|app)\.(jsx|tsx|js|ts|html|py)$/.test(p.toLowerCase()));
  const ui = files.filter((p) => /\.(jsx|tsx)$/.test(p) || /component|screen|page|view|ui/i.test(p));
  const state = files.filter((p) => /store|state|reducer|context/i.test(p));
  const api = files.filter((p) => /api|route|server|endpoint|fastapi|express/i.test(p));
  const styles = files.filter((p) => /\.(css|scss)$/.test(p));
  const data = files.filter((p) => /data|schema|model|seed|fixture|json/i.test(p));
  const build = files.filter((p) => /package\.json|vite|webpack|tsconfig|requirements|dockerfile|makefile/i.test(p));
  const central = files.map((p) => ({ path: p, score: (imports[p]?.length || 0) + (dependents[p]?.length || 0) * 2 })).sort((a, b) => b.score - a.score).slice(0, 8);
  const projectType = deps.includes('vite') && deps.includes('react') ? 'React/Vite app' : htmlFiles.length && files.length <= 8 ? 'Standalone HTML/static app' : files.some((p) => p.endsWith('.py')) ? 'Python or mixed project' : project?.spec?.stack || 'Imported codebase';
  const risks = [];
  if (!entryPoints.length) risks.push('No obvious entry point detected.');
  if (!build.length && !htmlFiles.length) risks.push('No build/static entry file detected.');
  if (files.some((p) => (fileMap[p] || '').split('\n').length > 500)) risks.push('One or more very large files may need splitting.');
  if (listFiles(project).some((f) => f.status === 'rejected')) risks.push('Some files are currently rejected by validation.');
  return { projectType, scripts, deps: deps.slice(0, 20), entryPoints, groups: { UI: ui, State: state, API: api, Styles: styles, Data: data, Build: build }, central, risks, imports, dependents, summary: `${projectType}. ${files.length} files, ${entryPoints.length} entry point(s), ${ui.length} UI file(s), ${state.length} state file(s), ${api.length} API file(s).` };
}
function quickDiff(before = '', after = '') { const a = before.split('\n'); const b = after.split('\n'); const max = Math.max(a.length, b.length); const rows = []; for (let i = 0; i < max; i += 1) if (a[i] !== b[i]) rows.push({ line: i + 1, before: a[i] ?? '', after: b[i] ?? '' }); return rows.slice(0, 80); }
function unique(list) { return [...new Set(list.filter(Boolean))]; }
function chooseCommandFiles(text, brain, project, selectedPath) {
  if (!project) return [];
  if (selectedPath && !wantsWholeProject(text)) return [selectedPath];
  const lower = (text || '').toLowerCase();
  const groups = brain?.groups || {};
  let candidates = [];
  if (/dark|theme|colour|color|style|design|layout|responsive|mobile|ui/.test(lower)) candidates = [...(groups.Styles || []), ...(groups.UI || []), ...(brain?.entryPoints || [])];
  else if (/state|save|store|data|inventory|score|auth|login/.test(lower)) candidates = [...(groups.State || []), ...(groups.Data || []), ...(groups.UI || []), ...(brain?.entryPoints || [])];
  else if (/api|server|backend|endpoint/.test(lower)) candidates = [...(groups.API || []), ...(groups.Data || []), ...(brain?.central || []).map((n) => n.path)];
  else candidates = [...(brain?.entryPoints || []), ...(brain?.central || []).map((n) => n.path), ...(groups.Styles || [])];
  if (selectedPath) candidates.unshift(selectedPath);
  return unique(candidates).filter((path) => project.files?.[path]?.content).slice(0, 6);
}

export default function App() {
  const [idea, setIdea] = useState('Build a React/Vite tower defense game with waves, enemies, towers, upgrades, HUD, canvas gameplay, specialist game architecture, and polished UI.');
  const [instruction, setInstruction] = useState('Use dependency topology and real npm build logs to repair the app until it runs.');
  const [project, setProject] = useState(null);
  const [workspace, setWorkspace] = useState(() => readWorkspace());
  const [selectedPath, setSelectedPath] = useState('');
  const [content, setContent] = useState('');
  const [inspection, setInspection] = useState(null);
  const [editInstruction, setEditInstruction] = useState('Refactor this file safely. Preserve imports, exports, and behaviour unless the request says otherwise.');
  const [command, setCommand] = useState('');
  const [chat, setChat] = useState([]);
  const [sandbox, setSandbox] = useState(null);
  const [logs, setLogs] = useState([]);
  const [pendingEdit, setPendingEdit] = useState(null);
  const [snapshots, setSnapshots] = useState([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');

  const projectId = project?.project_id;
  const files = listFiles(project);
  const brain = useMemo(() => project ? buildProjectBrain(project) : null, [project]);
  const previewUrl = sandbox?.preview_url ? API + sandbox.preview_url : '';

  useEffect(() => { if (!project?.project_id) return; const item = { project_id: project.project_id, name: project.spec?.app_name || 'Untitled project', stack: project.spec?.stack || '', status: project.status, files: files.length, updated_at: new Date().toISOString() }; const next = [item, ...workspace.filter((p) => p.project_id !== item.project_id)].slice(0, 20); setWorkspace(next); writeWorkspace(next); refreshSnapshots(project.project_id); }, [project?.project_id, project?.status, files.length]);

  async function request(path, options = {}) { const res = await fetch(API + path, options); const text = await res.text(); let data = null; try { data = text ? JSON.parse(text) : null; } catch {} if (!res.ok) throw new Error(data?.detail || text || `Request failed ${res.status}`); return data; }
  function post(path, body) { return request(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined }); }
  async function run(label, fn) { setBusy(true); setNotice(label); try { await fn(); } catch (err) { setNotice(`Failed: ${String(err.message || err)}`); } finally { setBusy(false); } }
  function addChat(role, text) { setChat((old) => [...old, { role, text, at: new Date().toLocaleTimeString() }].slice(-80)); }

  async function refreshSnapshots(id = projectId) { if (!id) return; try { const data = await request(`/projects/${id}/snapshots`); setSnapshots(data.snapshots || []); } catch { setSnapshots([]); } }
  async function snapshotNow(label = 'manual checkpoint') { if (!projectId) return; await run('Saving snapshot...', async () => { await post(`/projects/${projectId}/snapshot`, { label }); await refreshSnapshots(projectId); addChat('system', `Snapshot saved: ${label}`); }); }
  async function restoreSnapshot(snapshotId) { if (!projectId || !snapshotId) return; await run('Restoring snapshot...', async () => { const restored = await post(`/projects/${projectId}/restore/${snapshotId}`); setProject(restored); const first = selectedPath && restored.files?.[selectedPath] ? selectedPath : Object.keys(restored.files || {}).sort()[0] || ''; await selectFile(first, restored); await refreshSnapshots(restored.project_id); addChat('system', `Restored snapshot ${snapshotId}.`); }); }
  async function undoLastChange() { const latest = snapshots[0]; if (latest?.snapshot_id) await restoreSnapshot(latest.snapshot_id); }

  async function selectFile(path, nextProject = project) { setSelectedPath(path); setContent(nextProject?.files?.[path]?.content || ''); setPendingEdit(null); if (nextProject?.project_id && path) { try { setInspection(await request(`/projects/${nextProject.project_id}/files/${encodeURIComponent(path)}/inspect`)); } catch { setInspection(null); } } }
  async function refreshSandbox(id = projectId) { if (!id) return; const latest = await request(`/projects/${id}/sandbox/logs?limit=300`); setLogs(latest.logs || []); setSandbox(await request(`/projects/${id}/sandbox/status`)); }
  async function openWorkspaceProject(id) { await run('Opening workspace project...', async () => { const loaded = await post(`/projects/${id}/validate`); setProject(loaded); const first = Object.keys(loaded.files || {}).sort()[0] || ''; await selectFile(first, loaded); await refreshSnapshots(id); addChat('system', `Opened ${loaded.spec?.app_name || id}.`); }); }
  async function loadFolder(event) { await run('Loading folder into workbench...', async () => { const selected = Array.from(event.target.files || []).filter((file) => isTextFile(file.webkitRelativePath || file.name)); const pairs = await Promise.all(selected.slice(0, 500).map(async (file) => [file.webkitRelativePath || file.name, await file.text()])); const sourceFiles = Object.fromEntries(pairs.map(([path, text]) => [path.split('/').slice(1).join('/') || path, text])); const imported = await post('/projects/import/files', { name: selected[0]?.webkitRelativePath?.split('/')?.[0] || 'Imported Project', files: sourceFiles }); setProject(imported); const first = Object.keys(imported.files || {}).sort()[0] || ''; await selectFile(first, imported); await refreshSnapshots(imported.project_id); addChat('system', `Imported ${Object.keys(imported.files || {}).length} files. Project Brain is ready.`); }); }
  async function createProjectFromIdea(text = idea) { const created = await post('/projects', { idea: text, use_ai: true }); setProject(created); setSelectedPath(''); setContent(''); setInspection(null); await refreshSnapshots(created.project_id); return created; }
  async function createProject() { await run('Creating project...', async () => { const created = await createProjectFromIdea(idea); addChat('system', `Created plan for ${created.spec?.app_name || 'new project'}.`); }); }
  async function buildAll() { if (!projectId) return; await run('Building and repairing...', async () => { const built = await post(`/projects/${projectId}/build-all`); setProject(built); await refreshSnapshots(built.project_id); }); }
  async function validate() { if (!projectId) return; await run('Validating and repairing...', async () => { const validated = await post(`/projects/${projectId}/validate`); setProject(validated); await refreshSnapshots(validated.project_id); }); }
  async function runSandbox(id = projectId) { if (!id) return null; const result = await post(`/projects/${id}/sandbox/start`); setSandbox(result); await refreshSandbox(id); await refreshSnapshots(id); return result; }
  async function workErrors() { if (!projectId) return; await run('Working through errors...', async () => { let result = await runSandbox(); for (let round = 1; round <= 8; round += 1) { if (result?.build_ok) break; setNotice(`Repair round ${round}...`); result = await post(`/projects/${projectId}/sandbox/fix`, { instruction }); } setSandbox(result); await refreshSandbox(); await refreshSnapshots(projectId); addChat('codem8s', result?.build_ok ? 'Build is green and preview is live.' : 'I worked through repair rounds but it still needs attention.'); }); }
  async function autonomousMode(text = command || instruction) { if (!projectId) return; await run('Autonomous mode: working until it runs...', async () => { addChat('you', text || 'Work until it runs.'); const result = await post(`/projects/${projectId}/autonomous`, { instruction: text || 'Work through the project until it runs.', max_rounds: 12 }); if (result.project) setProject(result.project); if (result.sandbox) setSandbox(result.sandbox); await refreshSandbox(projectId); await refreshSnapshots(projectId); addChat('codem8s', result.project?.status === 'valid' ? 'Autonomous mode finished: project is valid and preview should be live.' : 'Autonomous mode reached a stopping point. Check logs or give me a narrower instruction.'); }); }

  async function saveFile(runAfter = selectedPath.endsWith('.html')) { if (!projectId || !selectedPath) return; await run(`Saving ${selectedPath}...`, async () => { await post(`/projects/${projectId}/snapshot`, { label: `before manual save ${selectedPath}` }); const saved = await post(`/projects/${projectId}/files/save`, { path: selectedPath, content, instruction: 'Manual workbench edit' }); setProject(saved); await selectFile(selectedPath, saved); await refreshSnapshots(saved.project_id); if (runAfter) await runSandbox(saved.project_id); addChat('system', runAfter ? `Saved and previewed ${selectedPath}.` : `Saved ${selectedPath}.`); }); }
  async function proposeEditFile(text = editInstruction) { if (!projectId || !selectedPath) return null; const original = content; await post(`/projects/${projectId}/snapshot`, { label: `before AI edit ${selectedPath}` }); const result = await post(`/projects/${projectId}/files/refactor`, { path: selectedPath, content, instruction: text }); const updated = result.file.content || ''; setPendingEdit({ kind: 'single', files: [{ path: selectedPath, before: original, after: updated, diff: quickDiff(original, updated) }], project: result.project, inspection: result.inspection, instruction: text }); setContent(original); await refreshSnapshots(result.project.project_id); addChat('codem8s', `Prepared changes for ${selectedPath}. Review the diff and approve or reject.`); return result; }
  async function proposeProjectCommand(text) { if (!projectId || !project) return null; const targets = chooseCommandFiles(text, brain, project, selectedPath); if (!targets.length) { addChat('codem8s', 'I could not find safe files to edit for that request. Select a file or ask for a narrower change.'); return null; } await post(`/projects/${projectId}/snapshot`, { label: `before command: ${text.slice(0, 60)}` }); let workingProject = project; const changes = []; for (const path of targets) { const before = workingProject.files?.[path]?.content || ''; if (!before) continue; setNotice(`Preparing ${path}...`); const result = await post(`/projects/${workingProject.project_id}/files/refactor`, { path, content: before, instruction: `${text}\n\nThis is part of a coordinated multi-file command. Preserve public APIs unless the request requires changing them.` }); const after = result.file.content || ''; workingProject = result.project; if (after !== before) changes.push({ path, before, after, diff: quickDiff(before, after) }); } await refreshSnapshots(workingProject.project_id); if (!changes.length) { addChat('codem8s', 'I checked the likely files but did not produce meaningful changes.'); return null; } setProject(workingProject); setPendingEdit({ kind: 'multi', files: changes, project: workingProject, inspection: null, instruction: text }); addChat('codem8s', `Prepared a multi-file change across ${changes.length} file(s). Review the diffs and approve or reject.`); return workingProject; }
  async function approvePendingEdit(runAfter = false) { if (!pendingEdit) return; setProject(pendingEdit.project); const selectedChange = pendingEdit.files.find((f) => f.path === selectedPath) || pendingEdit.files[0]; if (selectedChange) { setSelectedPath(selectedChange.path); setContent(selectedChange.after); try { setInspection(await request(`/projects/${pendingEdit.project.project_id}/files/${encodeURIComponent(selectedChange.path)}/inspect`)); } catch {} } addChat('system', `Approved AI change to ${pendingEdit.files.length} file(s).`); const id = pendingEdit.project.project_id; setPendingEdit(null); await refreshSnapshots(id); if (runAfter) await runSandbox(id); }
  async function rejectPendingEdit() { if (!pendingEdit) return; let restored = pendingEdit.project; for (const change of pendingEdit.files) restored = await post(`/projects/${restored.project_id}/files/save`, { path: change.path, content: change.before, instruction: 'Rejected AI change restore' }); setProject(restored); const selectedChange = pendingEdit.files.find((f) => f.path === selectedPath) || pendingEdit.files[0]; if (selectedChange) setContent(selectedChange.before); await refreshSnapshots(restored.project_id); addChat('system', `Rejected AI change and restored ${pendingEdit.files.length} file(s).`); setPendingEdit(null); }

  async function runUnifiedCommand() { const text = command.trim(); if (!text) return; setCommand(''); addChat('you', text); await run('Codem8s is working...', async () => { let activeProject = project; if (!activeProject) { activeProject = await createProjectFromIdea(text); addChat('codem8s', 'Created a new project from your request. Ask me to build/run it, or press Autonomous: Do Everything.'); return; } if (/\b(keep working|autonomous|do everything|finish it|until it runs|make it work)\b/i.test(text)) { const result = await post(`/projects/${activeProject.project_id}/autonomous`, { instruction: text, max_rounds: 12 }); if (result.project) setProject(result.project); if (result.sandbox) setSandbox(result.sandbox); await refreshSandbox(activeProject.project_id); await refreshSnapshots(activeProject.project_id); addChat('codem8s', 'Ran autonomous mode. I generated, repaired, built, and tried to preview the project.'); return; } if (/\b(explain|understand|architecture|brain|map|overview)\b/i.test(text) && brain) { addChat('codem8s', `Project Brain: ${brain.summary}\nEntry points: ${brain.entryPoints.join(', ') || 'none'}\nRisks: ${brain.risks.join('; ') || 'none'}`); return; } if (wantsWholeProject(text)) await proposeProjectCommand(text); else if (selectedPath) await proposeEditFile(text); else await proposeProjectCommand(text); }); }
  function exportZip() { if (projectId) window.location = `${API}/projects/${projectId}/export-snapshot`; }

  return (
    <main className="app">
      <h1>Codem8s Full Stack</h1><p>Generate projects or load an existing folder, inspect topology, edit files, ask Codem8s to change anything, then preview/export.</p><p><b>Backend:</b> {API}</p>
      {notice && <section className="card running"><b>{notice}</b>{busy && <div className="spinner" />}</section>}
      <section className="card workspace-card"><h2>Workspace</h2>{workspace.length === 0 ? <p>No recent projects yet.</p> : <div className="workspace-list">{workspace.map((item) => <button className="workspace-item" key={item.project_id} onClick={() => openWorkspaceProject(item.project_id)}><b>{item.name}</b><span>{item.status} · {item.files} files · {item.stack || 'unknown stack'}</span></button>)}</div>}</section>
      <section className="card snapshot-card"><h2>Snapshots / Undo</h2><div className="row"><button onClick={() => snapshotNow('manual checkpoint')} disabled={!projectId || busy}>Snapshot Now</button><button className="warning" onClick={undoLastChange} disabled={!projectId || !snapshots.length || busy}>Undo Last Change</button><button onClick={() => refreshSnapshots()} disabled={!projectId || busy}>Refresh Snapshots</button></div><div className="snapshot-list">{snapshots.length === 0 ? <p>No snapshots yet.</p> : snapshots.slice(0, 10).map((snap) => <div className="snapshot-item" key={snap.snapshot_id}><span><b>{snap.label || snap.snapshot_id}</b><br /><small>{snap.snapshot_id} · {snap.status || 'saved'}</small></span><button onClick={() => restoreSnapshot(snap.snapshot_id)} disabled={busy}>Restore</button></div>)}</div></section>
      <section className="card command-card"><h2>Ask Codem8s</h2><p>Examples: “explain this project”, “make this file cleaner”, “make the whole project dark mode”, “run it”, “make it work”.</p><textarea value={command} onChange={(e) => setCommand(e.target.value)} placeholder="Ask Codem8s to change, build, preview, repair, explain, or refactor..." /><div className="row action-row"><button onClick={runUnifiedCommand} disabled={busy}>Do It</button><button onClick={() => autonomousMode(command || instruction)} disabled={!projectId || busy}>Autonomous: Do Everything</button><button onClick={workErrors} disabled={!projectId || busy}>Make It Work</button><button onClick={exportZip} disabled={!projectId}>Export Snapshot</button></div><div className="chat-log">{chat.map((item, index) => <div className={`chat-line ${item.role}`} key={`${index}-${item.at}`}><b>{item.role}</b><span>{item.text}</span></div>)}</div></section>
      {pendingEdit && <section className="card diff-card"><h2>{pendingEdit.kind === 'multi' ? 'Multi-file AI Change Preview' : 'AI Change Preview'}</h2><p><b>{pendingEdit.files.length} file(s)</b> prepared. Approve to apply this version, or reject to restore the previous code.</p><div className="row"><button onClick={() => approvePendingEdit(false)}>Approve</button><button onClick={() => approvePendingEdit(true)}>Approve + Preview</button><button className="warning" onClick={() => run('Rejecting change...', rejectPendingEdit)}>Reject</button></div><div className="diff-list">{pendingEdit.files.map((file) => <div key={file.path}><h3>{file.path}</h3>{file.diff.map((row) => <div className="diff-row" key={`${file.path}-${row.line}`}><b>{row.line}</b><pre className="diff-before">- {row.before}</pre><pre className="diff-after">+ {row.after}</pre></div>)}</div>)}</div></section>}
      {brain && <section className="card brain-card"><h2>Project Brain</h2><p>{brain.summary}</p><div className="status-pills"><span className="pill">{brain.projectType}</span><span className="pill">scripts: {brain.scripts.join(', ') || 'none'}</span><span className="pill">deps: {brain.deps.slice(0, 4).join(', ') || 'none'}</span></div><div className="grid"><article><h3>Entry Points</h3>{brain.entryPoints.map((p) => <button className="graph-node" key={p} onClick={() => selectFile(p)}><span>{p}</span><em>open</em></button>)}</article><article><h3>Central Files</h3>{brain.central.map((n) => <button className="graph-node" key={n.path} onClick={() => selectFile(n.path)}><span>{n.path}</span><em>{n.score}</em></button>)}</article></div><div className="grid">{Object.entries(brain.groups).map(([name, group]) => <article key={name}><h3>{name}</h3>{group.slice(0, 8).map((p) => <button className="graph-node" key={p} onClick={() => selectFile(p)}><span>{p}</span><em>open</em></button>)}{group.length === 0 && <p>None detected</p>}</article>)}</div>{brain.risks.length > 0 && <pre className="bad-box log">{brain.risks.join('\n')}</pre>}</section>}
      <section className="card"><h2>Load Existing Project</h2><input type="file" webkitdirectory="true" directory="true" multiple onChange={loadFolder} /></section>
      <section className="card"><h2>Workbench</h2><div className="grid workbench-grid"><aside className="file-tree"><h3>Files</h3>{files.map((file) => <button className={file.path === selectedPath ? 'active file-button' : 'file-button'} key={file.path} onClick={() => selectFile(file.path)}>{file.path} · {file.status}</button>)}</aside><section><h3>{selectedPath || 'No file selected'}</h3><p>{inspection?.summary || 'Select a file to see its role, imports, dependents, and exports.'}</p>{inspection && <div className="status-pills"><span className="pill">{inspection.lines} lines</span><span className="pill">imports {inspection.imports.length}</span><span className="pill">used by {inspection.dependents.length}</span><span className="pill">exports {inspection.exports.length}</span></div>}<div className="grid"><pre className="log"><b>Imports</b>\n{inspection?.imports?.join('\n') || 'None'}</pre><pre className="log"><b>Dependents</b>\n{inspection?.dependents?.join('\n') || 'None'}</pre></div>{project?.files?.[selectedPath]?.errors?.length > 0 && <pre className="bad-box log">{project.files[selectedPath].errors.join('\n')}</pre>}<textarea className="code-editor" value={content} onChange={(e) => setContent(e.target.value)} /><h3>Selected-file edit request</h3><textarea value={editInstruction} onChange={(e) => setEditInstruction(e.target.value)} /><div className="row action-row"><button onClick={() => saveFile(false)} disabled={!selectedPath || busy}>Save File</button><button onClick={() => saveFile(true)} disabled={!selectedPath || busy}>Save + Preview</button><button onClick={() => run('Preparing AI edit...', () => proposeEditFile(editInstruction))} disabled={!selectedPath || busy}>Assistant Propose Edit</button><button onClick={validate} disabled={!projectId || busy}>Validate / Repair</button></div></section></div></section>
      <div className="grid"><section className="card"><h2>Generate New Project</h2><textarea value={idea} onChange={(e) => setIdea(e.target.value)} /><div className="row action-row"><button onClick={createProject} disabled={busy}>Create Plan</button><button onClick={buildAll} disabled={!projectId || busy}>Build All</button><button onClick={workErrors} disabled={!projectId || busy}>Work Through Errors</button></div>{project && <p><b>Status:</b> {project.status} | <b>Files:</b> {files.length}</p>}<h3>Instruction</h3><textarea value={instruction} onChange={(e) => setInstruction(e.target.value)} /></section><section className="card"><h2>Spec</h2><pre className="log">{project ? JSON.stringify(project.spec, null, 2) : 'No project yet'}</pre></section></div>
      <section className="card sandbox-card"><h2>Live Preview</h2>{sandbox && <p><b>Build:</b> {sandbox.build_ok ? 'OK' : 'not green'}<br /><b>Preview:</b> {sandbox.preview_url || 'none'}</p>}{previewUrl && <iframe className="preview-frame" title="Codem8s preview" src={previewUrl} />}{sandbox?.last_error && <pre className="log bad-box">{sandbox.last_error}</pre>}<pre className="log sandbox-log">{logs.length ? logs.join('\n') : 'No sandbox logs yet'}</pre></section><section className="card"><h2>Logs</h2><pre className="log">{project?.logs?.join('\n') || ''}</pre></section>
    </main>
  );
}
