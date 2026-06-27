import React from 'react';
import GoalPanel from './GoalPanel.jsx';
import App from './App.jsx';
import { ProjectProvider } from './projectContext.jsx';
import ProjectBridge from './projectBridge.jsx';

export default function AppWithGoal() {
  return (
    <ProjectProvider>
      <ProjectBridge />
      <div className="app">
        <GoalPanel />
      </div>
      <App />
    </ProjectProvider>
  );
}
