import React from 'react';

export default function CommandPanel({ command, setCommand, chat = [], busy, projectId, onRunCommand, onAutonomous, onMakeItWork, onExport }) {
  return (
    <section className="card command-card">
      <h2>Ask Codem8s</h2>
      <p>Examples: explain this project, make this file cleaner, make the whole project dark mode, run it, make it work.</p>
      <textarea value={command} onChange={(event) => setCommand && setCommand(event.target.value)} placeholder="Ask Codem8s to change, build, preview, repair, explain, or refactor..." />
      <div className="row action-row">
        <button onClick={onRunCommand} disabled={busy}>Do It</button>
        <button onClick={onAutonomous} disabled={!projectId || busy}>Autonomous: Do Everything</button>
        <button onClick={onMakeItWork} disabled={!projectId || busy}>Make It Work</button>
        <button onClick={onExport} disabled={!projectId}>Export Snapshot</button>
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
