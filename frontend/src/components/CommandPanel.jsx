import React, { useState } from 'react';

const API = import.meta.env.VITE_API_BASE_URL || 'https://codem8s-docker.onrender.com';

export default function CommandPanel({ command, setCommand, chat = [], busy, projectId, onRunCommand, onAutonomous, onMakeItWork, onExport }) {
  const [working, setWorking] = useState(false);

  async function buildThenMakeItWork() {
    if (!projectId || working) return;
    setWorking(true);
    try {
      // Build-all currently advances generation in bounded passes. Run several passes so
      // large plans do not stop with package/App/main still empty before sandbox repair.
      for (let pass = 0; pass < 4; pass += 1) {
        const response = await fetch(`${API}/projects/${projectId}/build-all`, { method: 'POST' });
        if (!response.ok) break;
        const project = await response.json().catch(() => null);
        const files = Object.values(project?.files || {});
        const emptyCount = files.filter((file) => !String(file?.content || '').trim()).length;
        if (emptyCount === 0) break;
      }
    } catch (error) {
      console.warn('Build-all before make-it-work failed; continuing repair flow', error);
    } finally {
      await onMakeItWork?.();
      setWorking(false);
    }
  }

  return (
    <section className="card command-card">
      <h2>Ask Codem8s</h2>
      <p>Examples: explain this project, make this file cleaner, make the whole project dark mode, run it, make it work.</p>
      <textarea value={command} onChange={(event) => setCommand && setCommand(event.target.value)} placeholder="Ask Codem8s to change, build, preview, repair, explain, or refactor..." />
      <div className="row action-row">
        <button onClick={onRunCommand} disabled={busy || working}>Do It</button>
        <button onClick={onAutonomous} disabled={!projectId || busy || working}>Autonomous: Do Everything</button>
        <button onClick={buildThenMakeItWork} disabled={!projectId || busy || working}>{working ? 'Building Files...' : 'Make It Work'}</button>
        <button onClick={onExport} disabled={!projectId || working}>Export Snapshot</button>
      </div>
      <div className="chat-log">
        {chat.map((item, index) => (
          <div className={`chat-line ${item.role}`} key={`${index}-${item.at || ''}`}>
            <b>{item.role}</b>
            <span>{item.text}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
