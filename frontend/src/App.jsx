import React, { useEffect, useMemo, useState } from 'react';

const API = import.meta.env.VITE_API_BASE_URL || 'https://codem8s.onrender.com';

export default function App() {
  const [idea, setIdea] = useState('Build a React/Vite tower defense game with waves, enemies, towers, upgrades, HUD, canvas gameplay, specialist game architecture, and polished UI.');
  const [instruction, setInstruction] = useState('Use the selected specialist agents, dependency topology, agent memory, and command output to fix the current build or quality error.');
  const [state, setState] = useState(null);
  const [settings, setSettings] = useState(null);
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('gpt-4o-mini');
  const [useAi, setUseAi] = useState(true);
  const [busy, setBusy] = useState(false);
  const [sandboxBusy, setSandboxBusy] = useState(false);
  const [error, setError] = useState('');
  const [sandbox, setSandbox] = useState(null);
  const [sandboxLogs, setSandboxLogs] = useState([]);
  const [agents, setAgents] = useState([]);
  const [teamRuns, setTeamRuns] = useState([]);
  const [memory, setMemory] = useState([]);
  const [quality, setQuality] = useState(null);
  const [graph, setGraph] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [snapshots, setSnapshots] = useState([]);

  const hasProject = Boolean(state?.project_id);
  const controlsLocked = busy || sandboxBusy;

  const progress = useMemo(() => {
    const files = Object.values(state?.files || {});
    const total = files.length;
    const valid = files.filter((file) => file.status === 'valid').length;
    const rejected = files.filter((file) => file.status === 'rejected').length;
    const generated = files.filter((file) => file.content).length;
    const generationComplete = total > 0 && valid + rejected >= total;
    return { files, total, valid, rejected, generated, generationComplete };
  }, [state]);

  useEffect(() => { loadSettings(); refreshAgents(); refreshMemory(); }, []);
  useEffect(() => { if (hasProject) refreshProjectMeta(); }, [state?.project_id, state?.status]);

  function unlockControls() {
    setBusy(false);
    setSandboxBusy(false);
    setError('Controls unlocked. Continue with Validate, Agent Team, Sandbox, or Export Snapshot.');
  }

  async function request(path, options = {}) {
    const response = await fetch(API + path, options);
    const text = await response.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = null; }
    if (!response.ok) throw new Error(data?.detail || text || `Request failed ${response.status}`);
    return data;
  }

  async function safeRun(fn, mode = 'main') {
    setError('');
    if (mode === 'sandbox') setSandboxBusy(true); else setBusy(true);
    try { return await fn(); }
    catch (err) { setError(String(err.message || err)); return null; }
    finally { if (mode === 'sandbox') setSandboxBusy(false); else setBusy(false); }
  }

  async function loadSettings() {
    try {
      const data = await request('/settings');
      setSettings(data);
      setModel(data.openai_model || 'gpt-4o-mini');
    } catch (err) { setError(String(err.message || err)); }
  }

  async function saveSettings() {
    await safeRun(async () => {
      const data = await request('/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ openai_api_key: apiKey, openai_model: model }) });
      setSettings(data); setApiKey('');
    });
  }

  async function refreshProjectMeta() {
    await Promise.allSettled([refreshAgents(), refreshTeamRuns(), refreshMemory(), refreshQuality(), refreshGraph(), refreshTimeline(), refreshSnapshots(), refreshSandboxLogs(false)]);
  }

  async function refreshAgents() {
    try { const data = await request('/agents'); setAgents(data.agents || []); } catch {}
  }

  async function refreshTeamRuns() {
    if (!hasProject) return;
    try { const data = await request(`/projects/${state.project_id}/team/runs`); setTeamRuns(data.team_runs || []); } catch {}
  }

  async function refreshMemory(query = '') {
    try {
      const path = query ? `/agent-memory?query=${encodeURIComponent(query)}&limit=30` : '/agent-memory?limit=30';
      const data = await request(path); setMemory(data.memory || []);
    } catch {}
  }

  async function refreshQuality() {
    if (!hasProject) return;
    try { setQuality(await request(`/projects/${state.project_id}/quality`)); } catch {}
  }

  async function refreshGraph() {
    if (!hasProject) return;
    try { setGraph(await request(`/projects/${state.project_id}/graph`)); } catch {}
  }

  async function refreshTimeline() {
    if (!hasProject) return;
    try { const data = await request(`/projects/${state.project_id}/timeline`); setTimeline(data.events || []); } catch {}
  }

  async function refreshSnapshots() {
    if (!hasProject) return;
    try { const data = await request(`/projects/${state.project_id}/snapshots`); setSnapshots(data.snapshots || []); } catch {}
  }

  async function refreshSandboxLogs(showError = true) {
    if (!hasProject) return;
    try {
      const data = await request(`/projects/${state.project_id}/sandbox/logs?limit=300`);
      setSandboxLogs(data.logs || []);
      const status = await request(`/projects/${state.project_id}/sandbox/status`);
      setSandbox(status);
    } catch (err) { if (showError) setError(String(err.message || err)); }
  }

  async function createProject() {
    await safeRun(async () => {
      setSandbox(null); setSandboxLogs([]); setQuality(null); setGraph(null); setTimeline([]); setSnapshots([]); setTeamRuns([]);
      const created = await request('/projects', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ idea, use_ai: useAi }) });
      setState(created);
      setTimeout(refreshProjectMeta, 300);
    });
  }

  async function buildNext() {
    if (!hasProject) return;
    await safeRun(async () => { setState(await request(`/projects/${state.project_id}/build-next`, { method: 'POST' })); await refreshProjectMeta(); });
  }

  async function buildAll() {
    if (!hasProject) return;
    await safeRun(async () => {
      let current = state;
      for (let i = 0; i < 100; i += 1) {
        const pending = Object.values(current.files || {}).filter((file) => file.status !== 'valid');
        if (!pending.length) break;
        current = await request(`/projects/${current.project_id}/build-next`, { method: 'POST' });
        setState(current);
        await new Promise((resolve) => setTimeout(resolve, 80));
      }
      // Always continue to validation/repair after file generation. Do not leave user stuck at planned/generated.
      const validated = await request(`/projects/${current.project_id}/validate`, { method: 'POST' });
      setState(validated);
      await refreshProjectMeta();
    });
  }

  async function validateProject() {
    if (!hasProject) return;
    await safeRun(async () => { setState(await request(`/projects/${state.project_id}/validate`, { method: 'POST' })); await refreshProjectMeta(); });
  }

  async function applyInstruction() {
    if (!hasProject || !instruction.trim()) return;
    await safeRun(async () => { setState(await request(`/projects/${state.project_id}/change`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ instruction }) })); await refreshProjectMeta(); });
  }

  async function runAgentTeam() {
    if (!hasProject) return;
    await safeRun(async () => {
      const result = await request(`/projects/${state.project_id}/team/run`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ goal: instruction, max_cycles: 1 }) });
      if (result.project) setState(result.project);
      await refreshProjectMeta();
    }, 'sandbox');
  }

  async function startSandbox() {
    if (!hasProject) return;
    await safeRun(async () => { setSandbox(await request(`/projects/${state.project_id}/sandbox/start`, { method: 'POST' })); await refreshSandboxLogs(); await refreshProjectMeta(); }, 'sandbox');
  }

  async function fixFromSandbox() {
    if (!hasProject) return;
    await safeRun(async () => {
      setSandbox(await request(`/projects/${state.project_id}/sandbox/fix`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ instruction }) }));
      await refreshSandboxLogs();
      await refreshProjectMeta();
    }, 'sandbox');
  }

  async function workThroughErrors() {
    if (!hasProject) return;
    await safeRun(async () => {
      let currentSandbox = await request(`/projects/${state.project_id}/sandbox/start`, { method: 'POST' });
      setSandbox(currentSandbox);
      let previous = '';
      for (let round = 1; round <= 8; round += 1) {
        await refreshSandboxLogs(false);
        if (currentSandbox?.build_ok) break;
        const signature = String(currentSandbox?.last_error || '').slice(-1500);
        if (signature && signature === previous) {
          setError('Paused because the same error repeated. Edit the instruction, then press Work Through Errors again.');
          break;
        }
        previous = signature;
        currentSandbox = await request(`/projects/${state.project_id}/sandbox/fix`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ instruction }) });
        setSandbox(currentSandbox);
      }
      await refreshSandboxLogs();
      await refreshProjectMeta();
    }, 'sandbox');
  }

  async function workUntilItRuns() {
    if (!hasProject) return;
    await safeRun(async () => {
      const encoded = encodeURIComponent(instruction || 'Work through the project until it runs.');
      await new Promise((resolve) => {
        const source = new EventSource(`${API}/projects/${state.project_id}/autonomous/stream?max_rounds=10&instruction=${encoded}`);
        source.onmessage = (event) => {
          try {
            const item = JSON.parse(event.data);
            setTimeline((items) => [...items, item]);
            if (item.detail) setSandboxLogs((lines) => [...lines.slice(-250), `[${item.title}] ${item.detail}`]);
            if (item.done) { source.close(); resolve(); }
          } catch { source.close(); resolve(); }
        };
        source.onerror = () => { source.close(); resolve(); };
      });
      await refreshSandboxLogs(false);
      await refreshProjectMeta();
    }, 'sandbox');
  }

  async function exportSnapshot() {
    if (!hasProject) return;
    if (state.status !== 'valid') setError('Exporting current snapshot even though build/quality is not green.');
    window.location = `${API}/projects/${state.project_id}/export-snapshot`;
  }

  function openPreview() {
    if (sandbox?.preview_url) window.open(sandbox.preview_url, '_blank', 'noopener,noreferrer');
  }

  const latestRun = teamRuns[0];

  return (
    <main className="app">
      <h1>Codem8s Full Stack</h1>
      <p>Generate files, then keep controls open for validation, agent repair, sandbox, and export.</p>
      <p><b>Backend:</b> {API}</p>
      {error && <section className="card bad"><b>Notice:</b> {error}</section>}

      <section className="card settings">
        <h2>OpenAI Settings</h2>
        <p className={settings?.has_api_key ? 'ok' : 'bad'}>{settings?.has_api_key ? `API key saved: ${settings.masked_api_key}` : 'No API key saved yet'}</p>
        <div className="row">
          <input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="Paste OpenAI API key once" />
          <input value={model} onChange={(event) => setModel(event.target.value)} />
          <button onClick={saveSettings} disabled={busy}>Save Settings</button>
          <button className="warning" onClick={unlockControls}>Unlock Controls</button>
        </div>
      </section>

      <div className="grid">
        <section className="card">
          <h2>Idea</h2>
          <textarea value={idea} onChange={(event) => setIdea(event.target.value)} />
          <label className="check"><input type="checkbox" checked={useAi} onChange={(event) => setUseAi(event.target.checked)} /> Use OpenAI for generation</label>
          <div className="row action-row">
            <button onClick={createProject} disabled={busy}>Create / Review Plan</button>
            <button onClick={buildNext} disabled={!hasProject || busy}>Build Next</button>
            <button onClick={buildAll} disabled={!hasProject || busy}>Approve Plan + Build All</button>
            <button onClick={validateProject} disabled={!hasProject || busy}>Validate / Repair</button>
            <button onClick={runAgentTeam} disabled={!hasProject || sandboxBusy}>Run Agent Team</button>
            <button onClick={startSandbox} disabled={!hasProject || sandboxBusy}>Run Sandbox</button>
            <button onClick={fixFromSandbox} disabled={!hasProject || sandboxBusy}>AI Fix + Re-run</button>
            <button onClick={workThroughErrors} disabled={!hasProject || sandboxBusy}>Work Through Errors</button>
            <button onClick={workUntilItRuns} disabled={!hasProject || sandboxBusy}>Work Until It Runs</button>
            <button onClick={exportSnapshot} disabled={!hasProject}>Export Snapshot</button>
          </div>
          {state && <p><b>Status:</b> {state.status} | <b>Progress:</b> {progress.valid}/{progress.total} valid | <b>Generated:</b> {progress.generated} | <b>Rejected:</b> {progress.rejected}</p>}
          {progress.generationComplete && state?.status !== 'valid' && <p className="warn">Files are generated. Continue with Validate / Repair, Agent Team, or Sandbox. Controls stay enabled.</p>}
          <h2>Steer While Building</h2>
          <textarea value={instruction} onChange={(event) => setInstruction(event.target.value)} />
          <button onClick={applyInstruction} disabled={!hasProject || busy}>Apply Instruction</button>
        </section>
        <section className="card"><h2>Spec</h2><pre className="log">{state ? JSON.stringify(state.spec, null, 2) : 'No project yet'}</pre></section>
      </div>

      <section className="card sandbox-card">
        <h2>Live Sandbox</h2>
        <div className="status-pills"><span className={sandbox?.running ? 'pill ok-bg' : 'pill'}>{sandbox?.running ? 'Running' : 'Stopped'}</span><span className={sandbox?.build_ok ? 'pill ok-bg' : 'pill bad-bg'}>{sandbox?.build_ok ? 'Build OK' : 'Build not green'}</span></div>
        <div className="row"><button onClick={() => refreshSandboxLogs()} disabled={!hasProject}>Refresh Logs</button><button onClick={openPreview} disabled={!sandbox?.preview_url}>Open Preview</button></div>
        {sandbox && <p><b>Preview:</b> {sandbox.preview_url || 'not started'}<br /><b>Root:</b> {sandbox.root || 'not created'}</p>}
        {sandbox?.last_error && <pre className="log bad-box">{sandbox.last_error}</pre>}
        <pre className="log sandbox-log">{sandboxLogs.length ? sandboxLogs.join('\n') : 'No sandbox logs yet'}</pre>
      </section>

      <section className="card agent-console">
        <h2>Agent Team Console</h2>
        <div className="agent-grid">{agents.map((agent) => <article className="agent-card" key={agent.agent_id}><b>{agent.name}</b><p>{agent.role}</p><div>{(agent.skills || []).slice(0, 6).map((skill) => <span className="tag" key={skill}>{skill}</span>)}</div></article>)}</div>
        <h3>Latest Team Run</h3>
        {latestRun ? <pre className="log">{(latestRun.handoffs || []).map((h) => `${h.agent}: ${h.summary}\n${(h.actions || []).join('\n')}`).join('\n\n')}</pre> : <p>No team runs yet.</p>}
      </section>

      <section className="card quality-card">
        <h2>Product Quality Score</h2>
        {quality ? <><div className="quality-score"><strong>{quality.total}/100</strong><span>overall</span></div><div className="quality-bars">{['product_architecture', 'ui_depth', 'workflow_depth', 'data_richness', 'design_system'].map((key) => <div className="quality-bar" key={key}><label>{key.replaceAll('_', ' ')}</label><div><span style={{ width: `${quality[key] || 0}%` }} /></div><b>{quality[key] || 0}</b></div>)}</div>{quality.issues?.map((issue) => <p className="bad" key={issue}>• {issue}</p>)}</> : <p>No quality score yet.</p>}
      </section>

      <section className="card graph-card">
        <h2>Dependency Graph Viewer</h2>
        <div className="graph-list">{(graph?.nodes || []).map((node) => <button key={node.path} className="graph-node"><span>{node.path}</span><em className={node.status === 'valid' ? 'ok' : 'bad'}>{node.status}</em></button>)}</div>
      </section>

      <section className="card memory-card">
        <h2>Agent Memory Viewer</h2>
        <div className="memory-list">{memory.map((item) => <article className="memory-item" key={item.memory_id}><b>{item.pattern}</b><p>{item.fix || item.lesson || item.symptom}</p><small>{item.category} · {(item.tags || []).join(', ')}</small></article>)}</div>
      </section>

      <section className="card timeline-card">
        <h2>Timeline</h2>
        <div className="timeline-list">{timeline.slice().reverse().map((event, index) => <div className={`timeline-item ${event.kind}`} key={`${index}-${event.detail}`}><b>{event.title}</b><span>{event.detail}</span></div>)}</div>
      </section>

      <section className="card snapshot-card">
        <h2>Snapshots</h2>
        <div className="snapshot-list">{snapshots.slice().reverse().map((item) => <div className="snapshot-item" key={item.snapshot_id}><span>{item.label}</span><span>{item.status}</span><span>{item.valid_count}/{item.file_count} valid</span></div>)}</div>
      </section>

      <section className="card"><h2>Files</h2>{progress.files.map((file) => <div className="file" key={file.path}><b>{file.path}</b> <span className={file.status === 'valid' ? 'ok' : 'bad'}>{file.status}</span>{file.content && <pre className="log">{file.content.slice(0, 1000)}</pre>}{file.errors?.length > 0 && <pre className="bad">{file.errors.join('\n')}</pre>}</div>)}</section>
      <section className="card"><h2>Logs</h2><pre className="log">{state?.logs?.join('\n') || ''}</pre></section>
    </main>
  );
}
