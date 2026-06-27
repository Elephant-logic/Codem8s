import { useEffect } from 'react';
import { useProject } from './projectContext.jsx';

export default function ProjectBridge() {
  const { project, sandbox, snapshots } = useProject();

  useEffect(() => {
    window.codem8sProject = project || null;
    window.codem8sSandbox = sandbox || null;
    window.codem8sSnapshots = snapshots || [];
  }, [project, sandbox, snapshots]);

  useEffect(() => {
    function handleStorage(event) {
      if (event.key === 'codem8s-workspace-v1') {
        window.dispatchEvent(new CustomEvent('codem8s-workspace-changed'));
      }
    }
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  return null;
}
