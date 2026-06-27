import React, { useEffect, useState } from 'react';
import { readItems, writeItems } from './goalStorage';

export default function GoalPanel() {
  const [items, setItems] = useState(() => readItems());
  const [text, setText] = useState('Build this project and get it running.');

  useEffect(() => {
    writeItems(items);
  }, [items]);

  function addItem() {
    const title = text.trim();
    if (!title) return;
    setItems((old) => [{ id: String(Date.now()), title, status: 'ready', tasks: ['Plan', 'Checkpoint', 'Build', 'Preview', 'Validate'] }, ...old].slice(0, 20));
  }

  function markDone(id) {
    setItems((old) => old.map((item) => item.id === id ? { ...item, status: 'done' } : item));
  }

  function removeItem(id) {
    setItems((old) => old.filter((item) => item.id !== id));
  }

  return (
    <section className="card goal-card">
      <h2>Goal Runner</h2>
      <p>Create a goal and track the work from idea to running preview.</p>
      <textarea value={text} onChange={(event) => setText(event.target.value)} />
      <button onClick={addItem}>Create Goal</button>
      <div className="goal-list">
        {items.length === 0 ? <p>No goals yet.</p> : items.map((item) => (
          <article className={`goal-item ${item.status}`} key={item.id}>
            <div className="row">
              <b>{item.title}</b>
              <span className="pill">{item.status}</span>
              <button onClick={() => markDone(item.id)}>Mark Done</button>
              <button className="warning" onClick={() => removeItem(item.id)}>Delete</button>
            </div>
            {item.tasks.map((task) => <div className="goal-step" key={task}>☐ {task}</div>)}
          </article>
        ))}
      </div>
    </section>
  );
}
