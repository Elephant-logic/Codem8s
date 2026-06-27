import React from 'react';
import GoalPanel from './GoalPanel.jsx';
import App from './App.jsx';

export default function AppWithGoal() {
  return (
    <>
      <div className="app">
        <GoalPanel />
      </div>
      <App />
    </>
  );
}
