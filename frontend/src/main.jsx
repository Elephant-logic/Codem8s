import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import GoalPanel from './GoalPanel.jsx';
import './styles.css';

createRoot(document.getElementById('root')).render(
  <>
    <div className="app">
      <GoalPanel />
    </div>
    <App />
  </>
);
