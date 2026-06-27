import React, { useEffect, useState } from 'react';
import { readItems, writeItems } from './goalStorage';

const API = import.meta.env.VITE_API_BASE_URL || 'https://codem8s-docker.onrender.com';

export default function GoalPanel({ project, setProject, setSandbox, refreshSandbox, refreshSnapshots, addChat, setNotice }) {
  const [items, setItems] = useState(() => readItems());
  const [text, setText] = useState('Build this project and get it running.');
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState('');
  const [lastPreview, setLastPreview] = useState(null);

  useEffect(() => {
    writeItems(items);
  }, [items]);

  async function request(path, options = {}) {
    const res = await fetch(API + path, options);
    const body = await res.text();
    let data = null;
    try { data = body ? JSON.parse(body) : null; } catch {}
    if (!res.ok) throw new Error(data?.detail || body || `Request failed ${res.status}`);
    return data;
  }

  function post(path, body) {
    return request(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
  }

  function updateItem(id, patch) {
    setItems((old) => old.map((item) => item.id === id ? { ...item, ...patch } : item));
  }

  function setTask(id, task, done) {
    setItems((old) => old.map((item) => item.id === id ? { ...item, tasks: item.tasks.map((entry) => entry.name === task ? { ...entry, done } : entry) } : item));
  }

  function addItem() {
    const title = text.trim();
    if (!title) return;
    const tasks = ['Plan', 'Checkpoint', 'Build', 'Preview', 'Repair pass', 'Validate'].map((name) => ({ name, done: false }));
    setItems((old) => [{ id: String(Date.now()), title, status: 'ready', projectId: project?.project_id || '', tasks }, ...old].slice(0, 20));
    addChat?.('system', `Goal created: ${title}`);
  }

  async function runItem(item) {
    setRunning(true);
    setMessage('Goal runner started');
    setNotice?.('Goal runner started');
    updateItem(item.id, { status: 'running' });
    addChat?.('goal', item.title);
    try {
      let active = project;
      if (!active) {
        setMessage('Creating project plan');
        active = await post('/projects', { idea: item.title, use_ai: true });
        setProject?.(active);
        updateItem(item.id, { projectId: active.project_id });
      }
      setTask(item.id, 'Plan', true);

      setMessage('Saving checkpoint');
      await post(`/projects/${active.project_id}/snapshot`, { label: `goal start ${item.title.slice(0, 40)}` });
      await refreshSnapshots?.(active.project_id);
      setTask(item.id, 'Checkpoint', true);

      setMessage('Building project');
      active = await post(`/projects/${active.project_id}/build-all`, {});
      setProject?.(active);
      setTask(item.id, 'Build', true);

      setMessage('Starting preview');
      let preview = await post(`/projects/${active.project_id}/sandbox/start`, {});
      setSandbox?.(preview);
      setLastPreview(preview);
      await refreshSandbox?.(active.project_id);
      setTask(item.id, 'Preview', Boolean(preview?.build_ok));

      let repaired = Boolean(preview?.build_ok);
      for (let round = 1; round <= 4 && !preview?.build_ok; round += 1) {
        setMessage(`Repair pass ${round}`);
        setNotice?.(`Goal repair pass ${round}`);
        preview = await post(`/projects/${active.project_id}/sandbox/fix`, { instruction: item.title });
        setSandbox?.(preview);
        setLastPreview(preview);
        await refreshSandbox?.(active.project_id);
        repaired = Boolean(preview?.build_ok);
      }
      setTask(item.id, 'Repair pass', repaired);

      setMessage('Validating project');
      active = await post(`/projects/${active.project_id}/validate`, {});
      setProject?.(active);
      await refreshSnapshots?.(active.project_id);
      setTask(item.id, 'Validate', active.status === 'valid');

      const ok = preview?.build_ok || active.status === 'valid';
      updateItem(item.id, { status: ok ? 'done' : 'blocked' });
      setMessage(ok ? 'Goal reached a runnable state' : 'Goal needs steering');
      addChat?.('codem8s', ok ? `Goal complete: ${item.title}` : `Goal blocked: ${item.title}`);
    } catch (err) {
      updateItem(item.id, { status: 'blocked' });
      setMessage(`Goal blocked: ${String(err.message || err)}`);
      addChat?.('codem8s', `Goal blocked: ${String(err.message || err)}`);
    } finally {
      setRunning(false);
    }
  }

  function removeItem(id) {
    setItems((old) => old.filter((item) => item.id !== id));
  }

  return (
    <section className="card goal-card">
      <h2>Goal Runner</h2>
      <p>Create a goal and run the current Codem8s project workflow from idea to preview.</p>
      {message && <p><b>{message}</b></p>}
      {project && <p><b>Using project:</b> {project.spec?.app_name || project.project_id} · {project.status}</p>}
      {lastPreview && <p><b>Last preview:</b> {lastPreview.build_ok ? 'green' : 'not green'} {lastPreview.preview_url || ''}</p>}
      {lastPreview?.last_error && <pre className="log bad-box">{lastPreview.last_error}</pre>}
      <textarea value={text} onChange={(event) => setText(event.target.value)} />
      <button onClick={addItem} disabled={running}>Create Goal</button>
      <div className="goal-list">
        {items.length === 0 ? <p>No goals yet.</p> : items.map((item) => (
          <article className={`goal-item ${item.status}`} key={item.id}>
            <div className="row">
              <b>{item.title}</b>
              <span className="pill">{item.status}</span>
              <button onClick={() => runItem(item)} disabled={running}>Run / Continue</button>
              <button className="warning" onClick={() => removeItem(item.id)} disabled={running}>Delete</button>
            </div>
            {(item.tasks || []).map((task) => <div className={`goal-step ${task.done ? 'done' : ''}`} key={task.name}>{task.done ? '☑' : '☐'} {task.name}</div>)}
          </article>
        ))}
      </div>
    </section>
  );
}
