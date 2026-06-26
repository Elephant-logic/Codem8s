import React, { useState } from 'react';

const API = import.meta.env.VITE_API_BASE_URL || 'https://codem8s-docker.onrender.com';
const TEXT_EXTENSIONS = ['.js', '.jsx', '.ts', '.tsx', '.css', '.html', '.json', '.md', '.py', '.txt', '.yml', '.yaml'];

function isTextFile(path) {
  return TEXT_EXTENSIONS.some((ext) => path.endsWith(ext)) || ['package.json', 'requirements.txt', 'Dockerfile', 'Makefile'].includes(path.split('/').pop());
}

function listFiles(project) {
  return Object.values(project?.files || {}).sort((a, b) => a.path.localeCompare(b.path));
}

export default function App() {
  const [idea, setIdea] = useState('Build a React/Vite tower defense game with waves, enemies, towers, upgrades, HUD, canvas gameplay, specialist game architecture, and polished UI.');
  const [instruction, setInstruction] = useState('Use dependency topology and real npm build logs to repair the app until it runs.');
  const [project, setProject] = useState(null);
  const [selectedPath, setSelectedPath] = useState('');
  const [content, setContent] = useState('');
  const [inspection, setInspection] = useState(null);
  const [editInstruction, setEditInstruction] = useState('Refactor this file safely. Preserve imports, exports, and behaviour unless the request says otherwise.');
  const [sandbox, setSandbox] = useState(null);
  const [logs, setLogs] = useState([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');

  const projectId = project?.project_id;
  const files = listFiles(project);

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

  async function selectFile(path, nextProject = project) {
    setSelectedPath(path);
    setContent(nextProject?.files?.[path]?.content || '');
    if (nextProject?.project_id && path) {
      try { setInspection(await request(`/projects/${nextProject.project_id}/files/${encodeURIComponent(path)}/inspect`)); }
      catch { setInspection(null); }
    }
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
      setNotice(`Imported ${Object.keys(imported.files || {}).length} files. Select a file and edit it.`);
    });
  }

  async function createProject() {
    await run('Creating project...', async () => {
      const created = await post('/projects', { idea, use_ai: true });
      setProject(created);
      setSelectedPath('');
      setContent('');
      setInspection(null);
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

  async function runSandbox() {
    if (!projectId) return;
    await run('Running sandbox build...', async () => {
      const result = await post(`/projects/${projectId}/sandbox/start`);
      setSandbox(result);
      const latest = await request(`/projects/${projectId}/sandbox/logs?limit=300`);
      setLogs(latest.logs || []);
    });
  }

  async function workErrors() {
    if (!projectId) return;
    await run('Working through errors...', async () => {
      let result = await post(`/projects/${projectId}/sandbox/start`);
      for (let round = 1; round <= 8; round += 1) {
        if (result.build_ok) break;
        setNotice(`Repair round ${round}...`);
        result = await post(`/projects/${projectId}/sandbox/fix`, { instruction });
      }
      setSandbox(result);
      const latest = await request(`/projects/${projectId}/sandbox/logs?limit=300`);
      setLogs(latest.logs || []);
    });
  }

  async function saveFile() {
    if (!projectId || !selectedPath) return;
    await run(`Saving ${selectedPath}...`, async () => {
      const saved = await post(`/projects/${projectId}/files/save`, { path: selectedPath, content, instruction: 'Manual workbench edit' });
      setProject(saved);
      await selectFile(selectedPath, saved);
    });
  }

  async function smartEditFile() {
    if (!projectId || !selectedPath) return;
    await run(`Editing ${selectedPath}...`, async () => {
      const result = await post(`/projects/${projectId}/files/refactor`, { path: selectedPath, content, instruction: editInstruction });
      setProject(result.project);
      setContent(result.file.content || '');
      setInspection(result.inspection || null);
    });
  }

  function exportZip() {
    if (projectId) window.location = `${API}/projects/${projectId}/export-snapshot`;
  }

  return (
    <main className="app">
      <h1>Codem8s Full Stack</h1>
      <p>Generate projects or load an existing folder, inspect topology, edit files, use the assistant to refactor, then build and repair.</p>
      <p><b>Backend:</b> {API}</p>
      {notice && <section className="card running"><b>{notice}</b>{busy && <div className="spinner" />}</section>}

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
            <h3>Ask assistant to edit this file</h3>
            <textarea value={editInstruction} onChange={(e) => setEditInstruction(e.target.value)} />
            <div className="row action-row"><button onClick={saveFile} disabled={!selectedPath || busy}>Save File</button><button onClick={smartEditFile} disabled={!selectedPath || busy}>Assistant Edit Selected File</button><button onClick={validate} disabled={!projectId || busy}>Validate / Repair</button><button onClick={runSandbox} disabled={!projectId || busy}>Run Sandbox</button></div>
          </section>
        </div>
      </section>

      <div className="grid">
        <section className="card">
          <h2>Generate New Project</h2>
          <textarea value={idea} onChange={(e) => setIdea(e.target.value)} />
          <div className="row action-row"><button onClick={createProject} disabled={busy}>Create Plan</button><button onClick={buildAll} disabled={!projectId || busy}>Build All</button><button onClick={workErrors} disabled={!projectId || busy}>Work Through Errors</button><button onClick={exportZip} disabled={!projectId}>Export Snapshot</button></div>
          {project && <p><b>Status:</b> {project.status} | <b>Files:</b> {files.length}</p>}
          <h3>Instruction</h3><textarea value={instruction} onChange={(e) => setInstruction(e.target.value)} />
        </section>
        <section className="card"><h2>Spec</h2><pre className="log">{project ? JSON.stringify(project.spec, null, 2) : 'No project yet'}</pre></section>
      </div>

      <section className="card sandbox-card"><h2>Sandbox</h2>{sandbox && <p><b>Build:</b> {sandbox.build_ok ? 'OK' : 'not green'}<br /><b>Preview:</b> {sandbox.preview_url || 'none'}</p>}{sandbox?.last_error && <pre className="log bad-box">{sandbox.last_error}</pre>}<pre className="log sandbox-log">{logs.length ? logs.join('\n') : 'No sandbox logs yet'}</pre></section>
      <section className="card"><h2>Logs</h2><pre className="log">{project?.logs?.join('\n') || ''}</pre></section>
    </main>
  );
}
