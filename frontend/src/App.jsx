import React, { useEffect, useMemo, useState } from 'react';

const API = import.meta.env.VITE_API_BASE_URL || 'https://codem8s.onrender.com';

export default function App() {
  const [idea, setIdea] = useState('Build a job tracking app with dashboard and notes');
  const [change, setChange] = useState('');
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const [settings, setSettings] = useState(null);
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('gpt-4o-mini');
  const [useAi, setUseAi] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => { loadSettings(); }, []);

  const progress = useMemo(() => {
    const files = state ? Object.values(state.files) : [];
    const total = files.length;
    const valid = files.filter((file) => file.status === 'valid').length;
    const rejected = files.filter((file) => file.status === 'rejected').length;
    return { total, valid, rejected, label: total ? `${valid}/${total} valid` : '0/0 valid' };
  }, [state]);

  async function request(url, options = {}) {
    setError('');
    const response = await fetch(API + url, options);
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(data?.detail || `Request failed: ${response.status}`);
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
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ openai_api_key: apiKey, openai_model: model }),
      });
      setSettings(data);
      setApiKey('');
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setBusy(false);
    }
  }

  async function post(url, body = {}) {
    setBusy(true);
    try {
      const data = await request(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      setState(data);
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setBusy(false);
    }
  }

  async function createProject() {
    await post('/projects', { idea, use_ai: useAi });
  }

  async function buildNext() {
    if (state) await post(`/projects/${state.project_id}/build-next`);
  }

  async function buildAll() {
    if (state) await post(`/projects/${state.project_id}/build-all`);
  }

  async function pauseBuild() {
    if (state) await post(`/projects/${state.project_id}/pause`);
  }

  async function resumeBuild() {
    if (state) await post(`/projects/${state.project_id}/resume`);
  }

  async function applyChange() {
    if (state && change.trim()) {
      await post(`/projects/${state.project_id}/change`, { instruction: change });
      setChange('');
    }
  }

  async function validate() {
    if (state) await post(`/projects/${state.project_id}/validate`);
  }

  function exportZip() {
    if (state) window.location = API + `/projects/${state.project_id}/export`;
  }

  return (
    <main className="app">
      <h1>Codem8s Full Stack</h1>
      <p>Locked spec. Build all. Pause/resume. Live steering. No fake code saved.</p>
      <p><b>Backend:</b> {API}</p>
      {error && <section className="card bad"><b>Error:</b> {error}</section>}

      <section className="card settings">
        <h2>OpenAI Settings</h2>
        <p className={settings?.has_api_key ? 'ok' : 'bad'}>
          {settings?.has_api_key ? `API key saved: ${settings.masked_api_key}` : 'No API key saved yet'}
        </p>
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
          <label className="check">
            <input type="checkbox" checked={useAi} onChange={(event) => setUseAi(event.target.checked)} />
            Use OpenAI for generation
          </label>
          <div className="row">
            <button onClick={createProject} disabled={busy}>Create Spec</button>
            <button onClick={buildNext} disabled={!state || busy}>Build Next</button>
            <button onClick={buildAll} disabled={!state || busy}>Build All</button>
            <button onClick={pauseBuild} disabled={!state || busy}>Pause</button>
            <button onClick={resumeBuild} disabled={!state || busy}>Resume</button>
            <button onClick={validate} disabled={!state || busy}>Validate</button>
            <button onClick={exportZip} disabled={!state}>Export Zip</button>
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

      <section className="card">
        <h2>Files</h2>
        {state && Object.values(state.files).map((file) => (
          <div className="file" key={file.path}>
            <b>{file.path}</b> <span className={file.status === 'valid' ? 'ok' : 'bad'}>{file.status}</span>
            {typeof file.attempts === 'number' && <span> attempts:{file.attempts}</span>}
            {file.content && <pre className="log">{file.content.slice(0, 1200)}</pre>}
            {file.errors?.length > 0 && <pre className="bad">{file.errors.join('\n')}</pre>}
          </div>
        ))}
      </section>

      <section className="card">
        <h2>Logs</h2>
        <pre className="log">{state?.logs?.join('\n') || ''}</pre>
      </section>
    </main>
  );
}
