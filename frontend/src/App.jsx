import React, { useEffect, useMemo, useState } from 'react';

const API = import.meta.env.VITE_API_BASE_URL || 'https://codem8s.onrender.com';

export default function App() {
  const [idea, setIdea] = useState('Build a job tracking app with dashboard and notes');
  const [change, setChange] = useState('');
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const [sandboxBusy, setSandboxBusy] = useState(false);
  const [sandbox, setSandbox] = useState(null);
  const [sandboxLogLines, setSandboxLogLines] = useState([]);
  const [sandboxInstruction, setSandboxInstruction] = useState('Use the blueprint, entry point, dependency topology, and command output to fix the current build error.');
  const [graph, setGraph] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [settings, setSettings] = useState(null);
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('gpt-4o-mini');
  const [useAi, setUseAi] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => { loadSettings(); }, []);
  useEffect(() => { if (state?.project_id) refreshGraph(); }, [state?.project_id, state?.status]);

  const progress = useMemo(() => {
    const files = state ? Object.values(state.files) : [];
    const total = files.length;
    const valid = files.filter((file) => file.status === 'valid').length;
    const rejected = files.filter((file) => file.status === 'rejected').length;
    return { total, valid, rejected, label: total ? `${valid}/${total} valid` : '0/0 valid' };
  }, [state]);

  const graphDetails = useMemo(() => {
    if (!graph || !selectedNode) return null;
    const imports = graph.edges.filter((edge) => edge.to === selectedNode.path).map((edge) => edge.from);
    const dependents = graph.edges.filter((edge) => edge.from === selectedNode.path).map((edge) => edge.to);
    const file = state?.files?.[selectedNode.path];
    return { imports, dependents, file };
  }, [graph, selectedNode, state]);

  async function request(url, options = {}) {
    setError('');
    const response = await fetch(API + url, options);
    const text = await response.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = null; }
    if (!response.ok) throw new Error(data?.detail || text || `Request failed: ${response.status}`);
    return data;
  }

  async function loadSettings() {
    try {
      const data = await request('/settings');
      setSettings(data);
      setModel(data.openai_model || 'gpt-4o-mini');
    } catch (err) {
      setError(String(err.message || err));
    }
  }

  async function saveSettings() {
    setBusy(true);
    try {
      const data = await request('/settings', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ openai_api_key: apiKey, openai_model: model }),
      });
      setSettings(data);
      setApiKey('');
    } catch (err) { setError(String(err.message || err)); }
    finally { setBusy(false); }
  }

  async function post(url, body = {}) {
    setBusy(true);
    try {
      const data = await request(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      setState(data);
      return data;
    } catch (err) { setError(String(err.message || err)); return null; }
    finally { setBusy(false); }
  }

  async function createProject() {
    setSandbox(null); setSandboxLogLines([]); setGraph(null); setSelectedNode(null);
    await post('/projects', { idea, use_ai: useAi });
  }

  async function buildNext() { if (state) await post(`/projects/${state.project_id}/build-next`); }

  async function buildAll() {
    if (!state) return;
    setBusy(true);
    let current = state;
    try {
      for (let i = 0; i < 80; i += 1) {
        const pending = Object.values(current.files || {}).filter((file) => file.status !== 'valid');
        if (!pending.length) break;
        const data = await request(`/projects/${current.project_id}/build-next`, { method: 'POST' });
        current = data; setState(data);
        await new Promise((resolve) => setTimeout(resolve, 150));
      }
      const validated = await request(`/projects/${current.project_id}/validate`, { method: 'POST' });
      setState(validated);
    } catch (err) {
      setError(`Build stopped: ${String(err.message || err)}. Press Build All again to continue from saved progress.`);
    } finally { setBusy(false); }
  }

  async function pauseBuild() { if (state) await post(`/projects/${state.project_id}/pause`); }
  async function resumeBuild() { if (state) await post(`/projects/${state.project_id}/resume`); }

  async function applyChange() {
    if (state && change.trim()) { await post(`/projects/${state.project_id}/change`, { instruction: change }); setChange(''); }
  }

  async function validate() { if (state) await post(`/projects/${state.project_id}/validate`); }

  async function exportZip() {
    if (!state) return;
    if (state.status !== 'valid') setError('Exporting current snapshot. Build is not green yet, but files will still download.');
    window.location = API + `/projects/${state.project_id}/export-snapshot`;
  }

  async function refreshGraph() {
    if (!state?.project_id) return;
    try {
      const data = await request(`/projects/${state.project_id}/graph`);
      setGraph(data);
      if (!selectedNode && data.nodes?.length) setSelectedNode(data.nodes[0]);
    } catch (err) { setError(String(err.message || err)); }
  }

  async function startSandbox() {
    if (!state) return;
    setSandboxBusy(true);
    try {
      const data = await request(`/projects/${state.project_id}/sandbox/start`, { method: 'POST' });
      setSandbox(data); await refreshSandboxLogs();
    } catch (err) { setError(String(err.message || err)); }
    finally { setSandboxBusy(false); }
  }

  async function stopSandboxRun() {
    if (!state) return;
    setSandboxBusy(true);
    try { const data = await request(`/projects/${state.project_id}/sandbox/stop`, { method: 'POST' }); setSandbox(data); await refreshSandboxLogs(); }
    catch (err) { setError(String(err.message || err)); }
    finally { setSandboxBusy(false); }
  }

  async function refreshSandboxStatus() {
    if (!state) return null;
    try { const data = await request(`/projects/${state.project_id}/sandbox/status`); setSandbox(data); return data; }
    catch (err) { setError(String(err.message || err)); return null; }
  }

  async function refreshSandboxLogs() {
    if (!state) return null;
    try {
      const data = await request(`/projects/${state.project_id}/sandbox/logs?limit=300`);
      setSandboxLogLines(data.logs || []);
      const status = await refreshSandboxStatus();
      return { logs: data.logs || [], status };
    } catch (err) { setError(String(err.message || err)); return null; }
  }

  async function fixFromSandbox() {
    if (!state) return null;
    setSandboxBusy(true);
    try {
      const data = await request(`/projects/${state.project_id}/sandbox/fix`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ instruction: sandboxInstruction }) });
      setSandbox(data); await refreshSandboxLogs(); await validate(); await refreshGraph();
      return data;
    } catch (err) { setError(String(err.message || err)); return null; }
    finally { setSandboxBusy(false); }
  }

  async function workThroughSandbox() {
    if (!state) return;
    setSandboxBusy(true); setError('');
    let previousSignature = '';
    try {
      let current = await request(`/projects/${state.project_id}/sandbox/start`, { method: 'POST' });
      setSandbox(current);
      for (let round = 1; round <= 8; round += 1) {
        const logData = await request(`/projects/${state.project_id}/sandbox/logs?limit=300`);
        setSandboxLogLines([...(logData.logs || []), `--- Work-through round ${round} ---`]);
        const signature = String(current?.last_error || '').slice(-1200);
        if (current?.build_ok) { await validate(); setError(''); break; }
        if (signature && signature === previousSignature) { setError('Work-through paused: the same error repeated. Add a steering instruction, then press Work Through again.'); break; }
        previousSignature = signature;
        current = await request(`/projects/${state.project_id}/sandbox/fix`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ instruction: sandboxInstruction }) });
        setSandbox(current); await refreshSandboxLogs(); await refreshGraph();
        await new Promise((resolve) => setTimeout(resolve, 250));
      }
    } catch (err) { setError(`Work-through stopped: ${String(err.message || err)}`); }
    finally { setSandboxBusy(false); }
  }

  async function refreshSandboxAll() { await refreshSandboxLogs(); }
  function openPreview() { if (sandbox?.preview_url) window.open(sandbox.preview_url, '_blank', 'noopener,noreferrer'); }

  return (
    <main className="app">
      <h1>Codem8s Full Stack</h1>
      <p>Locked spec. Build all. Pause/resume. Live steering. No fake code saved.</p>
      <p><b>Backend:</b> {API}</p>
      {error && <section className="card bad"><b>Error:</b> {error}</section>}

      <section className="card settings">
        <h2>OpenAI Settings</h2>
        <p className={settings?.has_api_key ? 'ok' : 'bad'}>{settings?.has_api_key ? `API key saved: ${settings.masked_api_key}` : 'No API key saved yet'}</p>
        <div className="row">
          <input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="Paste OpenAI API key once, or use Render env var" />
          <input value={model} onChange={(event) => setModel(event.target.value)} placeholder="Model" />
          <button onClick={saveSettings} disabled={busy}>Save Settings</button>
        </div>
        <small>Stored at: {settings?.config_path || 'loading...'}</small>
      </section>

      <div className="grid">
        <section className="card">
          <h2>Idea</h2>
          <textarea value={idea} onChange={(event) => setIdea(event.target.value)} />
          <label className="check"><input type="checkbox" checked={useAi} onChange={(event) => setUseAi(event.target.checked)} /> Use OpenAI for generation</label>
          <div className="row">
            <button onClick={createProject} disabled={busy}>Create Spec</button>
            <button onClick={buildNext} disabled={!state || busy}>Build Next</button>
            <button onClick={buildAll} disabled={!state || busy}>Build All</button>
            <button onClick={pauseBuild} disabled={!state || busy}>Pause</button>
            <button onClick={resumeBuild} disabled={!state || busy}>Resume</button>
            <button onClick={validate} disabled={!state || busy}>Validate</button>
            <button onClick={exportZip} disabled={!state}>Export Snapshot</button>
          </div>
          {state && <p><b>Status:</b> {state.status} | <b>Progress:</b> {progress.label} | <b>Rejected:</b> {progress.rejected}</p>}
          <h2>Steer While Building</h2>
          <textarea value={change} onChange={(event) => setChange(event.target.value)} placeholder="Add login, switch to SQLite, make it mobile first" />
          <button onClick={applyChange} disabled={!state || busy}>Apply Instruction</button>
        </section>

        <section className="card">
          <h2>Spec</h2>
          <pre className="log">{state ? JSON.stringify(state.spec, null, 2) : 'No project yet'}</pre>
        </section>
      </div>

      <section className="card graph-card">
        <div className="split-head">
          <div><h2>Project Topology</h2><p>Blueprint dependency map: what each file imports and what depends on it.</p></div>
          <button onClick={refreshGraph} disabled={!state}>Refresh Graph</button>
        </div>
        <div className="graph-grid">
          <div className="graph-list">
            {(graph?.nodes || []).map((node) => (
              <button key={node.path} className={`graph-node ${selectedNode?.path === node.path ? 'selected' : ''}`} onClick={() => setSelectedNode(node)}>
                <span>{node.path}</span>
                <em className={node.status === 'valid' ? 'ok' : 'bad'}>{node.status}</em>
              </button>
            ))}
            {!graph?.nodes?.length && <p>No graph yet.</p>}
          </div>
          <div className="graph-detail">
            {selectedNode ? (
              <>
                <h3>{selectedNode.path}</h3>
                <p><b>Status:</b> {selectedNode.status}</p>
                <p><b>Role:</b> {selectedNode.role || 'not set'}</p>
                <h4>Imports</h4>
                <pre className="log">{graphDetails?.imports?.length ? graphDetails.imports.join('\n') : 'none'}</pre>
                <h4>Used by</h4>
                <pre className="log">{graphDetails?.dependents?.length ? graphDetails.dependents.join('\n') : 'none'}</pre>
                {graphDetails?.file?.errors?.length > 0 && <pre className="bad">{graphDetails.file.errors.join('\n')}</pre>}
              </>
            ) : <p>Select a file.</p>}
          </div>
        </div>
      </section>

      <section className="card sandbox-card">
        <div className="split-head">
          <div><h2>Live Sandbox</h2><p>Runs dependency install, build, dev server, and shows the command line output.</p></div>
          <div className="status-pills"><span className={sandbox?.running ? 'pill ok-bg' : 'pill'}>{sandbox?.running ? 'Running' : 'Stopped'}</span><span className={sandbox?.build_ok ? 'pill ok-bg' : 'pill bad-bg'}>{sandbox?.build_ok ? 'Build OK' : 'Build not green'}</span></div>
        </div>
        <div className="row">
          <button onClick={startSandbox} disabled={!state || sandboxBusy}>Run Sandbox</button>
          <button onClick={stopSandboxRun} disabled={!state || sandboxBusy}>Stop Sandbox</button>
          <button onClick={refreshSandboxAll} disabled={!state || sandboxBusy}>Refresh Logs</button>
          <button onClick={openPreview} disabled={!sandbox?.preview_url}>Open Preview</button>
        </div>
        <h3>AI Fix From Sandbox</h3>
        <textarea value={sandboxInstruction} onChange={(event) => setSandboxInstruction(event.target.value)} placeholder="Tell AI what to try using the command output" />
        <div className="row"><button onClick={fixFromSandbox} disabled={!state || sandboxBusy}>AI Fix + Re-run</button><button onClick={workThroughSandbox} disabled={!state || sandboxBusy}>Work Through Errors</button></div>
        {sandbox && <div className="sandbox-status"><p><b>Preview:</b> {sandbox.preview_url || 'not started'}</p><p><b>Root:</b> {sandbox.root || 'not created'}</p>{sandbox.last_error && <pre className="log bad-box">{sandbox.last_error}</pre>}</div>}
        <pre className="log sandbox-log">{sandboxLogLines.length ? sandboxLogLines.join('\n') : 'No sandbox logs yet'}</pre>
      </section>

      <section className="card">
        <h2>Files</h2>
        {state && Object.values(state.files).map((file) => <div className="file" key={file.path}><b>{file.path}</b> <span className={file.status === 'valid' ? 'ok' : 'bad'}>{file.status}</span>{typeof file.attempts === 'number' && <span> attempts:{file.attempts}</span>}{file.content && <pre className="log">{file.content.slice(0, 1200)}</pre>}{file.errors?.length > 0 && <pre className="bad">{file.errors.join('\n')}</pre>}</div>)}
      </section>

      <section className="card"><h2>Logs</h2><pre className="log">{state?.logs?.join('\n') || ''}</pre></section>
    </main>
  );
}
