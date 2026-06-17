import React, { useEffect, useState } from 'react';

const API = 'http://localhost:8000';

export default function App() {
  const [idea, setIdea] = useState('Build Codem8s as a full-stack AI code factory');
  const [change, setChange] = useState('');
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const [settings, setSettings] = useState(null);
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('gpt-4o-mini');
  const [useAi, setUseAi] = useState(true);

  useEffect(() => { loadSettings(); }, []);

  async function loadSettings() {
    const response = await fetch(API + '/settings');
    const data = await response.json();
    setSettings(data);
    setModel(data.openai_model || 'gpt-4o-mini');
  }

  async function saveSettings() {
    setBusy(true);
    try {
      const response = await fetch(API + '/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ openai_api_key: apiKey, openai_model: model }),
      });
      const data = await response.json();
      setSettings(data);
      setApiKey('');
    } finally {
      setBusy(false);
    }
  }

  async function post(url, body) {
    setBusy(true);
    try {
      const response = await fetch(API + url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await response.json();
      setState(data);
    } finally {
      setBusy(false);
    }
  }

  async function createProject() {
    await post('/projects', { idea, use_ai: useAi });
  }

  async function buildNext() {
    if (state) await post(`/projects/${state.project_id}/build-next`, {});
  }

  async function applyChange() {
    if (state && change.trim()) {
      await post(`/projects/${state.project_id}/change`, { instruction: change });
      setChange('');
    }
  }

  async function validate() {
    if (state) await post(`/projects/${state.project_id}/validate`, {});
  }

  function exportZip() {
    if (state) window.location = API + `/projects/${state.project_id}/export`;
  }

  return (
    <main className="app">
      <h1>Codem8s Full Stack</h1>
      <p>API key stored locally. Locked spec. File-by-file build. Live steering. No fake code saved.</p>

      <section className="card settings">
        <h2>OpenAI Settings</h2>
        <p className={settings?.has_api_key ? 'ok' : 'bad'}>
          {settings?.has_api_key ? `API key saved: ${settings.masked_api_key}` : 'No API key saved yet'}
        </p>
        <div className="row">
          <input
            type="password"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            placeholder="Paste OpenAI API key once"
          />
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
            Use stored OpenAI API key for generation
          </label>
          <button onClick={createProject} disabled={busy}>Create Spec</button>
          <button onClick={buildNext} disabled={!state || busy}>Build Next File</button>
          <button onClick={validate} disabled={!state || busy}>Validate</button>
          <button onClick={exportZip} disabled={!state}>Export Zip</button>

          <h2>Steer While Building</h2>
          <textarea
            value={change}
            onChange={(event) => setChange(event.target.value)}
            placeholder="Add login, switch to SQLite, make it mobile first"
          />
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
