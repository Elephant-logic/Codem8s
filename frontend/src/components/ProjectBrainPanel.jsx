import React from 'react';

export default function ProjectBrainPanel({ brain, onSelectFile }) {
  if (!brain) return null;
  return (
    <section className="card brain-card">
      <h2>Project Brain</h2>
      <p>{brain.summary}</p>
      <div className="status-pills">
        <span className="pill">{brain.projectType}</span>
        <span className="pill">scripts: {brain.scripts.join(', ') || 'none'}</span>
        <span className="pill">deps: {brain.deps.slice(0, 4).join(', ') || 'none'}</span>
      </div>
      <div className="grid">
        <article>
          <h3>Entry Points</h3>
          {brain.entryPoints.map((path) => (
            <button className="graph-node" key={path} onClick={() => onSelectFile && onSelectFile(path)}>
              <span>{path}</span><em>open</em>
            </button>
          ))}
        </article>
        <article>
          <h3>Central Files</h3>
          {brain.central.map((node) => (
            <button className="graph-node" key={node.path} onClick={() => onSelectFile && onSelectFile(node.path)}>
              <span>{node.path}</span><em>{node.score}</em>
            </button>
          ))}
        </article>
      </div>
      <div className="grid">
        {Object.entries(brain.groups).map(([name, group]) => (
          <article key={name}>
            <h3>{name}</h3>
            {group.slice(0, 8).map((path) => (
              <button className="graph-node" key={path} onClick={() => onSelectFile && onSelectFile(path)}>
                <span>{path}</span><em>open</em>
              </button>
            ))}
            {group.length === 0 && <p>None detected</p>}
          </article>
        ))}
      </div>
      {brain.risks.length > 0 && <pre className="bad-box log">{brain.risks.join('\n')}</pre>}
    </section>
  );
}
