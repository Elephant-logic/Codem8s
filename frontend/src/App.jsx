import React, { useState } from 'react';

const API = import.meta.env.VITE_API_BASE_URL || 'https://codem8s-docker.onrender.com';
const TEXT_EXTENSIONS = ['.js', '.jsx', '.ts', '.tsx', '.css', '.html', '.json', '.md', '.py', '.txt', '.yml', '.yaml'];

function isTextFile(path) {
  return TEXT_EXTENSIONS.some((ext) => path.endsWith(ext)) || ['package.json', 'requirements.txt', 'Dockerfile', 'Makefile'].includes(path.split('/').pop());
}

function listFiles(project) {
  return Object.values(project?.files || {}).sort((a, b) => a.path.localeCompare(b.path));
}

function wantsRun(text) {
  return /\b(run|preview|build|sandbox|show|test|make it work)\b/i.test(text || '');
}

function wantsWholeProject(text) {
  return /\b(all files|whole project|entire project|everywhere|across the project|multi[- ]file|app wide|global)\b/i.test(text || '');
}

export default function App() {
  const [idea, setIdea] = useState('Build a React/Vite tower defense game with waves, enemies, towers, upgrades, HUD, canvas gameplay, specialist game architecture, and polished UI.');
  const [instruction, setInstruction] = useState('Use dependency topology and real npm build logs to repair the app until it runs.');
  const [project, setProject] = useState(null);
  const [selectedPath, setSelectedPath] = useState('');
  const [content, setContent] = useState('');
  const [inspection, setInspection] = useState(null);
  const [editInstruction, setEditInstruction] = useState('Refactor this file safely. Preserve imports, exports, and behaviour unless the request says otherwise.');
  const [command, setCommand] = useState('');
  const [chat, setChat] = useState([]);
  const [sandbox, setSandbox] = useState(null);
  const [logs, setLogs] = useState([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');

  const projectId = project?.project_id;
  const files = listFiles(project);
  const previewUrl = sandbox?.preview_url ? API + sandbox.preview_url : '';

  async function request(path, options = {}) {
    const res = await fetch(API + path, options);
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch {}
    if (!res.ok) throw new Error(data?.detail || text || `Request failed ${res.status}`);
    return data;
  }

  function post(path, body) {
    return request(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined });
  }

  async function run(label, fn) {
    setBusy(true);
    setNotice(label);
    try { await fn(); }
    catch (err) { setNotice(`Failed: ${String(err.message || err)}`); }
    finally { setBusy(false); }
  }

  function addChat(role, text) {
    setChat((old) => [...old, { role, text, at: new Date().toLocaleTimeString() }].slice(-60));
  }

  async function selectFile(path, nextProject = project) {
    setSelectedPath(path);
    setContent(nextProject?.files?.[path]?.content || '');
    if (nextProject?.project_id && path) {
      try { setInspection(await request(`/projects/${nextProject.project_id}/files/${encodeURIComponent(path)}/inspect`)); }
      catch { setInspection(null); }
    }
  }

  async function refreshSandbox(id = projectId) {
    if (!id) return;
    const latest = await request(`/projects/${id}/sandbox/logs?limit=300`);
    setLogs(latest.logs || []);
    setSandbox(await request(`/projects/${id}/sandbox/status`));
  }

  async function loadFolder(event) {
    await run('Loading folder into workbench...', async () => {
      const selected = Array.from(event.target.files || []).filter((file) => isTextFile(file.webkitRelativePath || file.name));
      const pairs = await Promise.all(selected.slice(0, 500).map(async (file) => [file.webkitRelativePath || file.name, await file.text()]));
      const sourceFiles = Object.fromEntries(pairs.map(([path, text]) => [path.split('/').slice(1).join('/') || path, text]));
      const imported = await post('/projects/import/files', { name: selected[0]?.webkitRelativePath?.split('/')?.[0] || 'Imported Project', files: sourceFiles });
      setProject(imported);
      const first = Object.keys(imported.files || {}).sort()[0] || '';
      await selectFile(first, imported);
      addChat('system', `Imported ${Object.keys(imported.files || {}).length} files. You can now ask for changes.`);
      setNotice(`Imported ${Object.keys(imported.files || {}).length} files. Select a file and edit it.`);
    });
  }

  async function createProjectFromIdea(text = idea) {
    const created = await post('/projects', { idea: text, use_ai: true });
    setProject(created);
    setSelectedPath('');
    setContent('');
    setInspection(null);
    return created;
  }

  async function createProject() {
    await run('Creating project...', async () => {
      const created = await createProjectFromIdea(idea);
      addChat('system', `Created plan for ${created.spec?.app_name || 'new project'}.`);
    });
  }

  async function buildAll() {
    if (!projectId) return;
    await run('Building and repairing...', async () => setProject(await post(`/projects/${projectId}/build-all`)));
  }

  async function validate() {
    if (!projectId) return;
    await run('Validating and repairing...', async () => setProject(await post(`/projects/${projectId}/validate`)));
  }

  async function runSandbox(id = projectId) {
    if (!id) return null;
    const result = await post(`/projects/${id}/sandbox/start`);
    setSandbox(result);
    await refreshSandbox(id);
    return result;
  }

  async function workErrors() {
    if (!projectId) return;
    await run('Working through errors...', async () => {
      let result = await runSandbox();
      for (let round = 1; round <= 8; round += 1) {
        if (result?.build_ok) break;
        setNotice(`Repair round ${round}...`);
        result = await post(`/projects/${projectId}/sandbox/fix`, { instruction });
      }
      setSandbox(result);
      await refreshSandbox();
      addChat('codem8s', result?.build_ok ? 'Build is green and preview is live.' : 'I worked through repair rounds but it still needs attention.');
    });
  }

  async function autonomousMode(text = command || instruction) {
    if (!projectId) return;
    await run('Autonomous mode: working until it runs...', async () => {
      addChat('you', text || 'Work until it runs.');
      const result = await post(`/projects/${projectId}/autonomous`, { instruction: text || 'Work through the project until it runs.', max_rounds: 12 });
      if (result.project) setProject(result.project);
      if (result.sandbox) setSandbox(result.sandbox);
      await refreshSandbox(projectId);
      addChat('codem8s', result.project?.status === 'valid' ? 'Autonomous mode finished: project is valid and preview should be live.' : 'Autonomous mode reached a stopping point. Check logs or give me a narrower instruction.');
    });
  }

  async function saveFile(runAfter = false) {
    if (!projectId || !selectedPath) return;
    await run(`Saving ${selectedPath}...`, async () => {
      const saved = await post(`/projects/${projectId}/files/save`, { path: selectedPath, content, instruction: 'Manual workbench edit' });
      setProject(saved);
      await selectFile(selectedPath, saved);
      if (runAfter) await runSandbox(saved.project_id);
      addChat('system', runAfter ? `Saved and previewed ${selectedPath}.` : `Saved ${selectedPath}.`);
    });
  }

  async function smartEditFile(text = editInstruction, runAfter = false) {
    if (!projectId || !selectedPath) return null;
    const result = await post(`/projects/${projectId}/files/refactor`, { path: selectedPath, content, instruction: text });
    setProject(result.project);
    setContent(result.file.content || '');
    setInspection(result.inspection || null);
    if (runAfter) await runSandbox(result.project.project_id);
    return result;
  }

  async function runUnifiedCommand() {
    const text = command.trim();
    if (!text) return;
    setCommand('');
    addChat('you', text);
    await run('Codem8s is working...', async () => {
      let activeProject = project;
      if (!activeProject) {
        activeProject = await createProjectFromIdea(text);
        addChat('codem8s', 'Created a new project from your request. Ask me to build/run it, or press Autonomous: Do Everything.');
        return;
      }
      if (/\b(keep working|autonomous|do everything|finish it|until it runs|make it work)\b/i.test(text)) {
        const result = await post(`/projects/${activeProject.project_id}/autonomous`, { instruction: text, max_rounds: 12 });
        if (result.project) setProject(result.project);
        if (result.sandbox) setSandbox(result.sandbox);
        await refreshSandbox(activeProject.project_id);
        addChat('codem8s', 'Ran autonomous mode. I generated, repaired, built, and tried to preview the project.');
        return;
      }
      if (wantsWholeProject(text)) {
        const changed = await post(`/projects/${activeProject.project_id}/change`, { instruction: text });
        setProject(changed);
        activeProject = changed;
        addChat('codem8s', 'Applied this as a project-wide instruction. Use Autonomous to execute it fully.');
      } else if (selectedPath) {
        const result = await smartEditFile(text, wantsRun(text));
        activeProject = result?.project || activeProject;
        addChat('codem8s', `Edited ${selectedPath}.${wantsRun(text) ? ' Preview was refreshed.' : ' Review the code and preview when ready.'}`);
      } else {
        const result = await post(`/projects/${activeProject.project_id}/team/run`, { goal: text, max_cycles: 1 });
        if (result.project) {
          setProject(result.project);
          activeProject = result.project;
        }
        addChat('codem8s', 'Ran the project agents on your request.');
      }
      if (wantsRun(text) && !selectedPath) {
        const result = await post(`/projects/${activeProject.project_id}/sandbox/start`);
        setSandbox(result);
        await refreshSandbox(activeProject.project_id);
        addChat('codem8s', result.build_ok ? 'Preview is live.' : 'Build/preview is not green yet. Press Autonomous or Make It Work.');
      }
    });
  }

  function exportZip() {
    if (projectId) window.location = `${API}/projects/${projectId}/export-snapshot`;
  }

  return (
    <main className="app">
      <h1>Codem8s Full Stack</h1>
      <p>Generate projects or load an existing folder, inspect topology, edit files, ask Codem8s to change anything, then preview/export.</p>
      <p><b>Backend:</b> {API}</p>
      {notice && <section className="card running"><b>{notice}</b>{busy && <div className="spinner" />}</section>}

      <section className="card command-card">
        <h2>Ask Codem8s</h2>
        <p>Examples: “make this file cleaner”, “make the whole project dark mode”, “run it”, “make it work”, “turn this into a one-file HTML app”.</p>
        <textarea value={command} onChange={(e) => setCommand(e.target.value)} placeholder="Ask Codem8s to change, build, preview, repair, explain, or refactor..." />
        <div className="row action-row"><button onClick={runUnifiedCommand} disabled={busy}>Do It</button><button onClick={() => autonomousMode(command || instruction)} disabled={!projectId || busy}>Autonomous: Do Everything</button><button onClick={workErrors} disabled={!projectId || busy}>Make It Work</button><button onClick={exportZip} disabled={!projectId}>Export Snapshot</button></div>
        <div className="chat-log">{chat.map((item, index) => <div className={`chat-line ${item.role}`} key={`${index}-${item.at}`}><b>{item.role}</b><span>{item.text}</span></div>)}</div>
      </section>

      <section className="card">
        <h2>Load Existing Project</h2>
        <input type="file" webkitdirectory="true" directory="true" multiple onChange={loadFolder} />
      </section>

      <section className="card">
        <h2>Workbench</h2>
        <div className="grid workbench-grid">
          <aside className="file-tree">
            <h3>Files</h3>
            {files.map((file) => <button className={file.path === selectedPath ? 'active file-button' : 'file-button'} key={file.path} onClick={() => selectFile(file.path)}>{file.path} · {file.status}</button>)}
          </aside>
          <section>
            <h3>{selectedPath || 'No file selected'}</h3>
            <p>{inspection?.summary || 'Select a file to see its role, imports, dependents, and exports.'}</p>
            {inspection && <div className="status-pills"><span className="pill">{inspection.lines} lines</span><span className="pill">imports {inspection.imports.length}</span><span className="pill">used by {inspection.dependents.length}</span><span className="pill">exports {inspection.exports.length}</span></div>}
            <div className="grid"><pre className="log"><b>Imports</b>\n{inspection?.imports?.join('\n') || 'None'}</pre><pre className="log"><b>Dependents</b>\n{inspection?.dependents?.join('\n') || 'None'}</pre></div>
            {project?.files?.[selectedPath]?.errors?.length > 0 && <pre className="bad-box log">{project.files[selectedPath].errors.join('\n')}</pre>}
            <textarea className="code-editor" value={content} onChange={(e) => setContent(e.target.value)} />
            <h3>Selected-file edit request</h3>
            <textarea value={editInstruction} onChange={(e) => setEditInstruction(e.target.value)} />
            <div className="row action-row"><button onClick={() => saveFile(false)} disabled={!selectedPath || busy}>Save File</button><button onClick={() => saveFile(true)} disabled={!selectedPath || busy}>Save + Preview</button><button onClick={() => run('Editing file...', () => smartEditFile(editInstruction, false))} disabled={!selectedPath || busy}>Assistant Edit</button><button onClick={() => run('Editing and previewing...', () => smartEditFile(editInstruction, true))} disabled={!selectedPath || busy}>Assistant Edit + Preview</button><button onClick={validate} disabled={!projectId || busy}>Validate / Repair</button></div>
          </section>
        </div>
      </section>

      <div className="grid">
        <section className="card">
          <h2>Generate New Project</h2>
          <textarea value={idea} onChange={(e) => setIdea(e.target.value)} />
          <div className="row action-row"><button onClick={createProject} disabled={busy}>Create Plan</button><button onClick={buildAll} disabled={!projectId || busy}>Build All</button><button onClick={workErrors} disabled={!projectId || busy}>Work Through Errors</button></div>
          {project && <p><b>Status:</b> {project.status} | <b>Files:</b> {files.length}</p>}
          <h3>Instruction</h3><textarea value={instruction} onChange={(e) => setInstruction(e.target.value)} />
        </section>
        <section className="card"><h2>Spec</h2><pre className="log">{project ? JSON.stringify(project.spec, null, 2) : 'No project yet'}</pre></section>
      </div>

      <section className="card sandbox-card"><h2>Live Preview</h2>{sandbox && <p><b>Build:</b> {sandbox.build_ok ? 'OK' : 'not green'}<br /><b>Preview:</b> {sandbox.preview_url || 'none'}</p>}{previewUrl && <iframe className="preview-frame" title="Codem8s preview" src={previewUrl} />}{sandbox?.last_error && <pre className="log bad-box">{sandbox.last_error}</pre>}<pre className="log sandbox-log">{logs.length ? logs.join('\n') : 'No sandbox logs yet'}</pre></section>
      <section className="card"><h2>Logs</h2><pre className="log">{project?.logs?.join('\n') || ''}</pre></section>
    </main>
  );
}
