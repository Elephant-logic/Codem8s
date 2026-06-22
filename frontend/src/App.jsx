import React, { useMemo, useState } from 'react';

const API = import.meta.env.VITE_API_BASE_URL || 'https://codem8s-docker.onrender.com';

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

  const projectId = state?.project_id;
  const files = Object.values(state?.files || {});
  const progress = useMemo(() => ({
    total: files.length,
    valid: files.filter((f) => f.status === 'valid').length,
    generated: files.filter((f) => f.content).length,
    rejected: files.filter((f) => f.status === 'rejected').length,
  }), [files]);

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

  async function refresh(id = projectId) {
    if (!id) return;
    await Promise.allSettled([
      request(`/projects/${id}/quality`).then(setQuality),
      request(`/agent-memory?limit=20`).then((d) => setMemory(d.memory || [])),
      request(`/projects/${id}/timeline`).then((d) => setTimeline(d.events || [])),
      refreshSandbox(id),
    ]);
  }

  async function refreshSandbox(id = projectId) {
    if (!id) return;
    const logs = await request(`/projects/${id}/sandbox/logs?limit=300`);
    setSandboxLogs(logs.logs || []);
    setSandbox(await request(`/projects/${id}/sandbox/status`));
  }

  async function runSandbox(id = projectId) {
    if (!id) return null;
    setNotice('Running live Docker sandbox: npm install then npm run build...');
    const result = await post(`/projects/${id}/sandbox/start`);
    setSandbox(result);
    await refreshSandbox(id);
    setNotice(result.build_ok ? 'Build passed. Preview ready.' : 'Build failed. Use AI Fix + Re-run or Work Through Errors.');
    return result;
  }

  async function createProject() {
    await run('Creating plan...', async () => {
      const created = await post('/projects', { idea, use_ai: true });
      setState(created); setSandbox(null); setSandboxLogs([]); await refresh(created.project_id);
      setNotice('Plan created. Press Approve + Build + Sandbox.');
    });
  }

  async function buildNext() {
    if (!projectId) return;
    await run('Building next file...', async () => {
      const next = await post(`/projects/${projectId}/build-next`);
      setState(next); await refresh(next.project_id);
    });
  }

  async function buildAllSandbox() {
    if (!projectId) return;
    await run('Generating files, repairing, then running live build...', async () => {
      let current = state;
      for (let i = 0; i < 100; i += 1) {
        const pending = Object.values(current.files || {}).filter((f) => f.status !== 'valid');
        if (!pending.length) break;
        setNotice(`Generating file ${i + 1}...`);
        current = await post(`/projects/${current.project_id}/build-next`);
        setState(current);
      }
      setNotice('Validating and repairing...');
      const validated = await post(`/projects/${current.project_id}/validate`);
      setState(validated); await refresh(validated.project_id); await runSandbox(validated.project_id);
    });
  }

  async function validateSandbox() {
    if (!projectId) return;
    await run('Validating, repairing, then running live build...', async () => {
      const validated = await post(`/projects/${projectId}/validate`);
      setState(validated); await refresh(validated.project_id); await runSandbox(validated.project_id);
    });
  }

  async function agentTeamSandbox() {
    if (!projectId) return;
    await run('Running agents, then live build...', async () => {
      const result = await post(`/projects/${projectId}/team/run`, { goal: instruction, max_cycles: 1 });
      if (result.project) setState(result.project);
      await refresh(result.project?.project_id || projectId); await runSandbox(result.project?.project_id || projectId);
    });
  }

  async function aiFix() {
    if (!projectId) return;
    await run('AI fixing from build logs...', async () => {
      const result = await post(`/projects/${projectId}/sandbox/fix`, { instruction });
      setSandbox(result); await refresh(projectId);
    });
  }

  async function workErrors() {
    if (!projectId) return;
    await run('Working through build errors...', async () => {
      let result = await runSandbox(projectId);
      let last = '';
      for (let round = 1; round <= 8; round += 1) {
        if (result?.build_ok) break;
        const sig = String(result?.last_error || '').slice(-1500);
        if (sig && sig === last) { setNotice('Paused: same error repeated.'); break; }
        last = sig;
        setNotice(`Repair round ${round}...`);
        result = await post(`/projects/${projectId}/sandbox/fix`, { instruction });
        setSandbox(result); await refreshSandbox(projectId);
      }
      await refresh(projectId);
    });
  }

  async function applyInstruction() {
    if (!projectId) return;
    await run('Applying instruction...', async () => {
      const changed = await post(`/projects/${projectId}/change`, { instruction });
      setState(changed); await refresh(changed.project_id);
    });
  }

  function openPreview() {
    if (sandbox?.preview_url) window.open(API + sandbox.preview_url, '_blank', 'noopener,noreferrer');
  }

  function exportZip() {
    if (projectId) window.location = `${API}/projects/${projectId}/export-snapshot`;
  }

  return (
    <main className="app">
      <h1>Codem8s Full Stack</h1>
      <p>Generate → repair → real npm build → sandbox preview → export.</p>
      <p><b>Backend:</b> {API}</p>
      {notice && <section className="card running"><b>{notice}</b>{busy && <div className="spinner" />}</section>}
      <div className="grid">
        <section className="card">
          <h2>Idea</h2>
          <textarea value={idea} onChange={(e) => setIdea(e.target.value)} />
          <div className="row action-row"><button onClick={createProject} disabled={busy}>Create / Review Plan</button><button onClick={buildNext} disabled={!projectId || busy}>Build Next</button><button onClick={buildAllSandbox} disabled={!projectId || busy}>Approve + Build + Sandbox</button><button onClick={validateSandbox} disabled={!projectId || busy}>Validate / Repair + Sandbox</button><button onClick={agentTeamSandbox} disabled={!projectId || busy}>Run Agents + Sandbox</button><button onClick={() => runSandbox()} disabled={!projectId || busy}>Run Sandbox Build</button><button onClick={aiFix} disabled={!projectId || busy}>AI Fix + Re-run</button><button onClick={workErrors} disabled={!projectId || busy}>Work Through Errors</button><button onClick={exportZip} disabled={!projectId}>Export Snapshot</button></div>
          {state && <p><b>Status:</b> {state.status} | <b>Progress:</b> {progress.valid}/{progress.total} valid | <b>Generated:</b> {progress.generated} | <b>Rejected:</b> {progress.rejected}</p>}
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
