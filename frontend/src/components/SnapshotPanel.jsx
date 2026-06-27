import React from 'react';

export default function SnapshotPanel({ snapshots = [], projectId, busy, onSnapshot, onUndo, onRefresh, onRestore }) {
  return (
    <section className="card snapshot-card">
      <h2>Snapshots / Undo</h2>
      <div className="row">
        <button onClick={() => onSnapshot && onSnapshot('manual checkpoint')} disabled={!projectId || busy}>Snapshot Now</button>
        <button className="warning" onClick={onUndo} disabled={!projectId || !snapshots.length || busy}>Undo Last Change</button>
        <button onClick={onRefresh} disabled={!projectId || busy}>Refresh Snapshots</button>
      </div>
      <div className="snapshot-list">
        {snapshots.length === 0 ? (
          <p>No snapshots yet.</p>
        ) : snapshots.slice(0, 10).map((snap) => (
          <div className="snapshot-item" key={snap.snapshot_id}>
            <span>
              <b>{snap.label || snap.snapshot_id}</b><br />
              <small>{snap.snapshot_id} - {snap.status || 'saved'}</small>
            </span>
            <button onClick={() => onRestore && onRestore(snap.snapshot_id)} disabled={busy}>Restore</button>
          </div>
        ))}
      </div>
    </section>
  );
}
