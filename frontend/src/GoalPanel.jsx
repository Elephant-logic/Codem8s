import React, { useEffect, useState } from 'react';
import { readItems, writeItems } from './goalStorage';

const API = import.meta.env.VITE_API_BASE_URL || 'https://codem8s-docker.onrender.com';

export default function GoalPanel() {
  const [items, setItems] = useState(() => readItems());
  const [text, setText] = useState('Build this project and get it running.');
  const [activeProject, setActiveProject] = useState(null);
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState('');

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
    setItems((old) => [{ id: String(Date.now()), title, status: 'ready', projectId: activeProject?.project_id || '', tasks }, ...old].slice(0, 20));
  }

  async function runItem(item) {
    setRunning(true);
    setMessage('Goal runner started');
    updateItem(item.id, { status: 'running' });
    try {
      let project = activeProject;
      if (!project) {
        setMessage('Creating project plan');
        project = await post('/projects', { idea: item.title, use_ai: true });
        setActiveProject(project);
        updateItem(item.id, { projectId: project.project_id });
      }
      setTask(item.id, 'Plan', true);

      setMessage('Saving checkpoint');
      await post(`/projects/${project.project_id}/snapshot`, { label: `goal start ${item.title.slice(0, 40)}` });
      setTask(item.id, 'Checkpoint', true);

      setMessage('Building project');
      project = await post(`/projects/${project.project_id}/build-all`, {});
      setActiveProject(project);
      setTask(item.id, 'Build', true);

      setMessage('Starting preview');
      let preview = await post(`/projects/${project.project_id}/sandbox/start`, {});
      setTask(item.id, 'Preview', Boolean(preview?.build_ok));

      if (!preview?.build_ok) {
        setMessage('Running repair pass');
        preview = await post(`/projects/${project.project_id}/sandbox/fix`, { instruction: item.title });
      }
      setTask(item.id, 'Repair pass', Boolean(preview?.build_ok));

      setMessage('Validating project');
      project = await post(`/projects/${project.project_id}/validate`, {});
      setActiveProject(project);
      setTask(item.id, 'Validate', project.status === 'valid');

      const ok = preview?.build_ok || project.status === 'valid';
      updateItem(item.id, { status: ok ? 'done' : 'blocked' });
      setMessage(ok ? 'Goal reached a runnable state' : 'Goal needs steering');
    } catch (err) {
      updateItem(item.id, { status: 'blocked' });
      setMessage(`Goal blocked: ${String(err.message || err)}`);
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
      <p>Create a goal and run the project workflow from idea to preview.</p>
      {message && <p><b>{message}</b></p>}
      <textarea value={text} onChange={(event) => setText(event.target.value)} />
      <button onClick={addItem} disabled={running}>Create Goal</button>
      <div className="goal-list">
        {items.length === 0 ? <p>No goals yet.</p> : items.map((item) => (
          <article className={`goal-item ${item.status}`} key={item.id}>
            <div className="row">
              <b>{item.title}</b>
              <span className="pill">{item.status}</span>
              <button onClick={() => runItem(item)} disabled={running}>Run Goal</button>
              <button className="warning" onClick={() => removeItem(item.id)} disabled={running}>Delete</button>
            </div>
            {(item.tasks || []).map((task) => <div className={`goal-step ${task.done ? 'done' : ''}`} key={task.name}>{task.done ? '☑' : '☐'} {task.name}</div>)}
          </article>
        ))}
      </div>
    </section>
  );
}
