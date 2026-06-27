import React from 'react';

export default function LivePreviewPanel({ sandbox, previewUrl, logs = [] }) {
  return (
    <section className="card sandbox-card">
      <h2>Live Preview</h2>
      {sandbox && (
        <p>
          <b>Build:</b> {sandbox.build_ok ? 'OK' : 'not green'}<br />
          <b>Preview:</b> {sandbox.preview_url || 'none'}
        </p>
      )}
      {previewUrl && <iframe className="preview-frame" title="Codem8s preview" src={previewUrl} />}
      {sandbox?.last_error && <pre className="log bad-box">{sandbox.last_error}</pre>}
      <pre className="log sandbox-log">{logs.length ? logs.join('\n') : 'No sandbox logs yet'}</pre>
    </section>
  );
}
