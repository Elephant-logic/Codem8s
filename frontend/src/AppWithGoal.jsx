import React from 'react';
import GoalPanel from './GoalPanel.jsx';
import App from './App.jsx';
import { ProjectProvider } from './projectContext.jsx';

export default function AppWithGoal() {
  return (
    <ProjectProvider>
      <div className="app">
        <GoalPanel />
      </div>
      <App />
    </ProjectProvider>
  );
}
