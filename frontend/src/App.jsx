import React, { useEffect, useMemo, useState } from 'react';
import { WorkspacePanel, SnapshotPanel, CommandPanel, LivePreviewPanel, ProjectBrainPanel } from './components';
import { useProject, API } from './projectContext.jsx';

const TEXT_EXTENSIONS = ['.js', '.jsx', '.ts', '.tsx', '.css', '.html', '.json', '.md', '.py', '.txt', '.yml', '.yaml'];
const WORKSPACE_KEY = 'codem8s-workspace-v1';

function isTextFile(path) { return TEXT_EXTENSIONS.some((ext) => path.endsWith(ext)) || ['package.json', 'requirements.txt', 'Dockerfile', 'Makefile'].includes(path.split('/').pop()); }
function listFiles(project) { return Object.values(project?.files || {}).sort((a, b) => a.path.localeCompare(b.path)); }
function wantsWholeProject(text) { return /\b(all files|whole project|entire project|everywhere|across the project|multi[- ]file|app wide|global|app|site|ui|theme|layout)\b/i.test(text || ''); }
function readWorkspace() { try { return JSON.parse(localStorage.getItem(WORKSPACE_KEY) || '[]'); } catch { return []; } }
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

// NOTE: this component is mounted inside <ProjectProvider> (see AppWithGoal.jsx) and shares
// project/sandbox/logs/snapshots/notice with GoalPanel via useProject(). There is exactly one
// copy of "current project" state; both panels read and write the same context.
export default function App() {
  const {
    project, setProject, sandbox, setSandbox, logs, snapshots, notice, setNotice,
    request, post, refreshSnapshots, refreshSandbox, runSandbox: ctxRunSandbox,
    buildAllIncremental, restoreSnapshot: ctxRestoreSnapshot,
  } = useProject();

  const [idea, setIdea] = useState('Build a React/Vite tower defense game with waves, enemies, towers, upgrades, HUD, canvas gameplay, specialist game architecture, and polished UI.');
  const [instruction, setInstruction] = useState('Use dependency topology and real npm build logs to repair the app until it runs.');
  const [workspace, setWorkspace] = useState(() => readWorkspace());
  const [selectedPath, setSelectedPath] = useState('');
  const [content, setContent] = useState('');
  const [inspection, setInspection] = useState(null);
  const [editInstruction, setEditInstruction] = useState('Refactor this file safely. Preserve imports, exports, and behaviour unless the request says otherwise.');
  const [command, setCommand] = useState('');
  const [chat, setChat] = useState([]);
  const [pendingEdit, setPendingEdit] = useState(null);
  const [busy, setBusy] = useState(false);
  const [selfTest, setSelfTest] = useState(null);

  const projectId = project?.project_id;
  const files = listFiles(project);
  const brain = useMemo(() => project ? buildProjectBrain(project) : null, [project]);
  const previewUrl = sandbox?.preview_url ? API + sandbox.preview_url : '';

  useEffect(() => {
    function onWorkspaceUpdate() { setWorkspace(readWorkspace()); }
    window.addEventListener('codem8s-workspace-updated', onWorkspaceUpdate);
    return () => window.removeEventListener('codem8s-workspace-updated', onWorkspaceUpdate);
  }, []);

  useEffect(() => {
    function onChatEvent(event) { addChat(event.detail?.role || 'system', event.detail?.text || ''); }
    window.addEventListener('codem8s-chat-event', onChatEvent);
    return () => window.removeEventListener('codem8s-chat-event', onChatEvent);
  }, []);

  async function run(label, fn) { setBusy(true); setNotice(label); try { await fn(); } catch (err) { setNotice(`Failed: ${String(err.message || err)}`); } finally { setBusy(false); } }
  function addChat(role, text) { setChat((old) => [...old, { role, text, at: new Date().toLocaleTimeString() }].slice(-80)); }

  async function snapshotNow(label = 'manual checkpoint') { if (!projectId) return; await run('Saving snapshot...', async () => { await post(`/projects/${projectId}/snapshot`, { label }); await refreshSnapshots(projectId); addChat('system', `Snapshot saved: ${label}`); }); }
  async function restoreSnapshot(snapshotId) { if (!projectId || !snapshotId) return; await run('Restoring snapshot...', async () => { const restored = await ctxRestoreSnapshot(snapshotId); const first = selectedPath && restored.files?.[selectedPath] ? selectedPath : Object.keys(restored.files || {}).sort()[0] || ''; await selectFile(first, restored); addChat('system', `Restored snapshot ${snapshotId}.`); }); }
  async function undoLastChange() { const latest = snapshots[0]; if (latest?.snapshot_id) await restoreSnapshot(latest.snapshot_id); }

  async function selectFile(path, nextProject = project) { setSelectedPath(path); setContent(nextProject?.files?.[path]?.content || ''); setPendingEdit(null); if (nextProject?.project_id && path) { try { setInspection(await request(`/projects/${nextProject.project_id}/files/${encodeURIComponent(path)}/inspect`)); } catch { setInspection(null); } } }
  async function openWorkspaceProject(id) { await run('Opening workspace project...', async () => { const loaded = await post(`/projects/${id}/validate`); setProject(loaded); const first = Object.keys(loaded.files || {}).sort()[0] || ''; await selectFile(first, loaded); await refreshSnapshots(id); addChat('system', `Opened ${loaded.spec?.app_name || id}.`); }); }
  async function loadFolder(event) { await run('Loading folder into workbench...', async () => { const selected = Array.from(event.target.files || []).filter((file) => isTextFile(file.webkitRelativePath || file.name)); const pairs = await Promise.all(selected.slice(0, 500).map(async (file) => [file.webkitRelativePath || file.name, await file.text()])); const sourceFiles = Object.fromEntries(pairs.map(([path, text]) => [path.split('/').slice(1).join('/') || path, text])); const imported = await post('/projects/import/files', { name: selected[0]?.webkitRelativePath?.split('/')?.[0] || 'Imported Project', files: sourceFiles }); setProject(imported); const first = Object.keys(imported.files || {}).sort()[0] || ''; await selectFile(first, imported); await refreshSnapshots(imported.project_id); addChat('system', `Imported ${Object.keys(imported.files || {}).length} files. Project Brain is ready.`); }); }

  async function createProjectFromIdea(text = idea) { const created = await post('/projects', { idea: text, use_ai: true }); setProject(created); setSelectedPath(''); setContent(''); setInspection(null); await refreshSnapshots(created.project_id); return created; }
  async function createProject() { await run('Creating project...', async () => { const created = await createProjectFromIdea(idea); addChat('system', `Created plan for ${created.spec?.app_name || 'new project'}.`); }); }
  async function buildAll() {
    if (!projectId) return;
    await run('Building and repairing...', async () => {
      const built = await buildAllIncremental(projectId, (step, remaining) => setNotice(`Building file ${step} (${remaining} remaining)...`));
      addChat('system', built?.status === 'complete' || built?.status === 'valid' ? 'Build finished.' : 'Build stopped before all files were valid — check Workbench for rejected files.');
    });
  }
  async function validate() { if (!projectId) return; await run('Validating and repairing...', async () => { const validated = await post(`/projects/${projectId}/validate`); setProject(validated); await refreshSnapshots(validated.project_id); }); }
  async function runSandbox(id = projectId) { if (!id) return null; await run('Running sandbox...', () => ctxRunSandbox(id)); return sandbox; }
  async function workErrors() { if (!projectId) return; await run('Working through errors...', async () => { let result = await ctxRunSandbox(projectId); for (let round = 1; round <= 8; round += 1) { if (result?.build_ok) break; setNotice(`Repair round ${round}...`); result = await post(`/projects/${projectId}/sandbox/fix`, { instruction }); } setSandbox(result); await refreshSandbox(projectId); await refreshSnapshots(projectId); addChat('codem8s', result?.build_ok ? 'Build is green and preview is live.' : 'I worked through repair rounds but it still needs attention.'); }); }
  async function autonomousMode(text = command || instruction) { if (!projectId) return; await run('Autonomous mode: working until it runs...', async () => { addChat('you', text || 'Work until it runs.'); const result = await post(`/projects/${projectId}/autonomous`, { instruction: text || 'Work through the project until it runs.', max_rounds: 12 }); if (result.project) setProject(result.project); if (result.sandbox) setSandbox(result.sandbox); await refreshSandbox(projectId); await refreshSnapshots(projectId); addChat('codem8s', result.project?.status === 'valid' ? 'Autonomous mode finished: project is valid and preview should be live.' : 'Autonomous mode reached a stopping point. Check logs or give me a narrower instruction.'); }); }

  async function saveFile(runAfter = selectedPath.endsWith('.html')) { if (!projectId || !selectedPath) return; await run(`Saving ${selectedPath}...`, async () => { await post(`/projects/${projectId}/snapshot`, { label: `before manual save ${selectedPath}` }); const saved = await post(`/projects/${projectId}/files/save`, { path: selectedPath, content, instruction: 'Manual workbench edit' }); setProject(saved); await selectFile(selectedPath, saved); await refreshSnapshots(saved.project_id); if (runAfter) await ctxRunSandbox(saved.project_id); addChat('system', runAfter ? `Saved and previewed ${selectedPath}.` : `Saved ${selectedPath}.`); }); }
  async function proposeEditFile(text = editInstruction) { if (!projectId || !selectedPath) return null; const original = content; await post(`/projects/${projectId}/snapshot`, { label: `before AI edit ${selectedPath}` }); const result = await post(`/projects/${projectId}/files/refactor`, { path: selectedPath, content, instruction: text }); const updated = result.file.content || ''; setPendingEdit({ kind: 'single', files: [{ path: selectedPath, before: original, after: updated, diff: quickDiff(original, updated) }], project: result.project, inspection: result.inspection, instruction: text }); setContent(original); await refreshSnapshots(result.project.project_id); addChat('codem8s', `Prepared changes for ${selectedPath}. Review the diff and approve or reject.`); return result; }
  async function proposeProjectCommand(text) {
    if (!projectId || !project) return null;
    // Prefer the backend's topology-aware planner (project_commander.py); fall back to the
    // local keyword heuristic only if that call fails for any reason.
    let targets = [];
    try {
      const plan = await post(`/projects/${projectId}/command/plan`, { instruction: text, selected_path: selectedPath || null });
      targets = (plan?.files || []).filter((path) => project.files?.[path]?.content);
    } catch {
      targets = [];
    }
    if (!targets.length) targets = chooseCommandFiles(text, brain, project, selectedPath);
    if (!targets.length) { addChat('codem8s', 'I could not find safe files to edit for that request. Select a file or ask for a narrower change.'); return null; }
    await post(`/projects/${projectId}/snapshot`, { label: `before command: ${text.slice(0, 60)}` });
    let workingProject = project; const changes = [];
    for (const path of targets) {
      const before = workingProject.files?.[path]?.content || '';
      if (!before) continue;
      setNotice(`Preparing ${path}...`);
      const result = await post(`/projects/${workingProject.project_id}/files/refactor`, { path, content: before, instruction: `${text}\n\nThis is part of a coordinated multi-file command. Preserve public APIs unless the request requires changing them.` });
      const after = result.file.content || '';
      workingProject = result.project;
      if (after !== before) changes.push({ path, before, after, diff: quickDiff(before, after) });
    }
    await refreshSnapshots(workingProject.project_id);
    if (!changes.length) { addChat('codem8s', 'I checked the likely files but did not produce meaningful changes.'); return null; }
    setProject(workingProject);
    setPendingEdit({ kind: 'multi', files: changes, project: workingProject, inspection: null, instruction: text });
    addChat('codem8s', `Prepared a multi-file change across ${changes.length} file(s). Review the diffs and approve or reject.`);
    return workingProject;
  }
  async function approvePendingEdit(runAfter = false) { if (!pendingEdit) return; setProject(pendingEdit.project); const selectedChange = pendingEdit.files.find((f) => f.path === selectedPath) || pendingEdit.files[0]; if (selectedChange) { setSelectedPath(selectedChange.path); setContent(selectedChange.after); try { setInspection(await request(`/projects/${pendingEdit.project.project_id}/files/${encodeURIComponent(selectedChange.path)}/inspect`)); } catch {} } addChat('system', `Approved AI change to ${pendingEdit.files.length} file(s).`); const id = pendingEdit.project.project_id; setPendingEdit(null); await refreshSnapshots(id); if (runAfter) await ctxRunSandbox(id); }
  async function rejectPendingEdit() { if (!pendingEdit) return; let restored = pendingEdit.project; for (const change of pendingEdit.files) restored = await post(`/projects/${restored.project_id}/files/save`, { path: change.path, content: change.before, instruction: 'Rejected AI change restore' }); setProject(restored); const selectedChange = pendingEdit.files.find((f) => f.path === selectedPath) || pendingEdit.files[0]; if (selectedChange) setContent(selectedChange.before); await refreshSnapshots(restored.project_id); addChat('system', `Rejected AI change and restored ${pendingEdit.files.length} file(s).`); setPendingEdit(null); }

  async function runUnifiedCommand() { const text = command.trim(); if (!text) return; setCommand(''); addChat('you', text); await run('Codem8s is working...', async () => { let activeProject = project; if (!activeProject) { activeProject = await createProjectFromIdea(text); addChat('codem8s', 'Created a new project from your request. Ask me to build/run it, or press Autonomous: Do Everything.'); return; } if (/\b(keep working|autonomous|do everything|finish it|until it runs|make it work)\b/i.test(text)) { const result = await post(`/projects/${activeProject.project_id}/autonomous`, { instruction: text, max_rounds: 12 }); if (result.project) setProject(result.project); if (result.sandbox) setSandbox(result.sandbox); await refreshSandbox(activeProject.project_id); await refreshSnapshots(activeProject.project_id); addChat('codem8s', 'Ran autonomous mode. I generated, repaired, built, and tried to preview the project.'); return; } if (/\b(explain|understand|architecture|brain|map|overview)\b/i.test(text) && brain) { let memoryNote = ''; try { const mem = await request(`/agent-memory?query=${encodeURIComponent(text)}&limit=3`); const records = mem?.records || mem || []; if (Array.isArray(records) && records.length) memoryNote = '\n\nRelevant past issues/decisions:\n' + records.map((r) => `- [${r.category || 'note'}] ${r.symptom || r.pattern || ''}${r.fix ? ` → ${r.fix}` : ''}`).join('\n'); } catch {} addChat('codem8s', `Project Brain: ${brain.summary}\nEntry points: ${brain.entryPoints.join(', ') || 'none'}\nRisks: ${brain.risks.join('; ') || 'none'}${memoryNote}`); return; } if (wantsWholeProject(text)) await proposeProjectCommand(text); else if (selectedPath) await proposeEditFile(text); else await proposeProjectCommand(text); }); }
  function exportZip() { if (projectId) window.location = `${API}/projects/${projectId}/export-snapshot`; }
  async function checkCodem8s() {
    setSelfTest(null);
    await run('Checking Codem8s (create, build, sandbox, memory)...', async () => {
      const result = await post('/selftest', {});
      setSelfTest(result);
    });
  }

  return (
    <main className="app">
      <h1>Codem8s Full Stack</h1><p>Generate projects or load an existing folder, inspect topology, edit files, ask Codem8s to change anything, then preview/export.</p><p><b>Backend:</b> {API}</p>
      {notice && <section className="card running"><b>{notice}</b>{busy && <div className="spinner" />}</section>}
      <section className="card">
        <h2>Check Codem8s</h2>
        <p>Runs Codem8s's own create → build → sandbox → memory loop against a known tiny app and reports exactly which stage fails, without touching your current project.</p>
        <div className="row action-row"><button onClick={checkCodem8s} disabled={busy}>Check Codem8s</button></div>
        {selfTest && (
          <div className="self-test-results">
            <p><b>{selfTest.ok ? 'All stages passed' : `${selfTest.passed}/${selfTest.total} stages passed`}</b></p>
            {selfTest.stages.map((s) => (
              <div key={s.stage} className={s.ok ? 'pill ok' : 'pill bad'}>
                <b>{s.ok ? '✓' : '✗'} {s.stage}</b> ({s.seconds}s) — {s.detail}
              </div>
            ))}
          </div>
        )}
      </section>
      <WorkspacePanel workspace={workspace} onOpenProject={openWorkspaceProject} />
      <SnapshotPanel snapshots={snapshots} projectId={projectId} busy={busy} onSnapshot={snapshotNow} onUndo={undoLastChange} onRefresh={() => refreshSnapshots()} onRestore={restoreSnapshot} />
      <CommandPanel command={command} setCommand={setCommand} chat={chat} busy={busy} projectId={projectId} onRunCommand={runUnifiedCommand} onAutonomous={() => autonomousMode(command || instruction)} onMakeItWork={workErrors} onExport={exportZip} />
      {pendingEdit && <section className="card diff-card"><h2>{pendingEdit.kind === 'multi' ? 'Multi-file AI Change Preview' : 'AI Change Preview'}</h2><p><b>{pendingEdit.files.length} file(s)</b> prepared. Approve to apply this version, or reject to restore the previous code.</p><div className="row"><button onClick={() => approvePendingEdit(false)}>Approve</button><button onClick={() => approvePendingEdit(true)}>Approve + Preview</button><button className="warning" onClick={() => run('Rejecting change...', rejectPendingEdit)}>Reject</button></div><div className="diff-list">{pendingEdit.files.map((file) => <div key={file.path}><h3>{file.path}</h3>{file.diff.map((row) => <div className="diff-row" key={`${file.path}-${row.line}`}><b>{row.line}</b><pre className="diff-before">- {row.before}</pre><pre className="diff-after">+ {row.after}</pre></div>)}</div>)}</div></section>}
      <ProjectBrainPanel brain={brain} onSelectFile={selectFile} />
      <section className="card"><h2>Load Existing Project</h2><input type="file" webkitdirectory="true" directory="true" multiple onChange={loadFolder} /></section>
      <section className="card"><h2>Workbench</h2><div className="grid workbench-grid"><aside className="file-tree"><h3>Files</h3>{files.map((file) => <button className={file.path === selectedPath ? 'active file-button' : 'file-button'} key={file.path} onClick={() => selectFile(file.path)}>{file.path} · {file.status}</button>)}</aside><section><h3>{selectedPath || 'No file selected'}</h3><p>{inspection?.summary || 'Select a file to see its role, imports, dependents, and exports.'}</p>{inspection && <div className="status-pills"><span className="pill">{inspection.lines} lines</span><span className="pill">imports {inspection.imports.length}</span><span className="pill">used by {inspection.dependents.length}</span><span className="pill">exports {inspection.exports.length}</span></div>}<div className="grid"><pre className="log"><b>Imports</b>\n{inspection?.imports?.join('\n') || 'None'}</pre><pre className="log"><b>Dependents</b>\n{inspection?.dependents?.join('\n') || 'None'}</pre></div>{project?.files?.[selectedPath]?.errors?.length > 0 && <pre className="bad-box log">{project.files[selectedPath].errors.join('\n')}</pre>}<textarea className="code-editor" value={content} onChange={(e) => setContent(e.target.value)} /><h3>Selected-file edit request</h3><textarea value={editInstruction} onChange={(e) => setEditInstruction(e.target.value)} /><div className="row action-row"><button onClick={() => saveFile(false)} disabled={!selectedPath || busy}>Save File</button><button onClick={() => saveFile(true)} disabled={!selectedPath || busy}>Save + Preview</button><button onClick={() => run('Preparing AI edit...', () => proposeEditFile(editInstruction))} disabled={!selectedPath || busy}>Assistant Propose Edit</button><button onClick={validate} disabled={!projectId || busy}>Validate / Repair</button></div></section></div></section>
      <div className="grid"><section className="card"><h2>Generate New Project</h2><textarea value={idea} onChange={(e) => setIdea(e.target.value)} /><div className="row action-row"><button onClick={createProject} disabled={busy}>Create Plan</button><button onClick={buildAll} disabled={!projectId || busy}>Build All</button><button onClick={workErrors} disabled={!projectId || busy}>Work Through Errors</button></div>{project && <p><b>Status:</b> {project.status} | <b>Files:</b> {files.length}</p>}<h3>Instruction</h3><textarea value={instruction} onChange={(e) => setInstruction(e.target.value)} /></section><section className="card"><h2>Spec</h2><pre className="log">{project ? JSON.stringify(project.spec, null, 2) : 'No project yet'}</pre></section></div>
      <LivePreviewPanel sandbox={sandbox} previewUrl={previewUrl} logs={logs} />
      <section className="card"><h2>Logs</h2><pre className="log">{project?.logs?.join('\n') || ''}</pre></section>
    </main>
  );
}
