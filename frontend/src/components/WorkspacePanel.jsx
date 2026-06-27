import React from 'react';

export default function WorkspacePanel({ workspace = [], onOpenProject }) {
  return (
    <section className="card workspace-card">
      <h2>Workspace</h2>
      {workspace.length === 0 ? (
        <p>No recent projects yet.</p>
      ) : (
        <div className="workspace-list">
          {workspace.map((item) => (
            <button className="workspace-item" key={item.project_id} onClick={() => onOpenProject && onOpenProject(item.project_id)}>
              <b>{item.name}</b>
              <span>{item.status} - {item.files} files - {item.stack || 'unknown stack'}</span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
