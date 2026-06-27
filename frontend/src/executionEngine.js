export const STAGES = ['Plan', 'Checkpoint', 'Build', 'Preview', 'Repair', 'Validate'];

export function freshTasks() {
  return STAGES.map((name) => ({ name, status: 'todo', done: false, note: '' }));
}

export function markTask(tasks = [], name, status, note = '') {
  return tasks.map((task) => task.name === name ? { ...task, status, done: status === 'done', note } : task);
}

export function nextOpenStage(tasks = []) {
  const open = tasks.find((task) => task.status !== 'done');
  return open?.name || 'Done';
}

export async function runExecutionPipeline({
  goal,
  project,
  createProject,
  post,
  onProject,
  onSandbox,
  onMessage,
  onTask,
  onEvent,
  maxRepairRounds = 4,
}) {
  let active = project;
  let sandbox = null;
  const emit = (message) => {
    onMessage?.(message);
    onEvent?.({ at: new Date().toISOString(), message });
  };
  const task = (name, status, note = '') => onTask?.(name, status, note);

  emit('Planning');
  task('Plan', 'running');
  if (!active) active = await createProject(goal.title);
  onProject?.(active);
  task('Plan', 'done', active.spec?.app_name || active.project_id);

  emit('Saving checkpoint');
  task('Checkpoint', 'running');
  await post(`/projects/${active.project_id}/snapshot`, { label: `goal start ${goal.title.slice(0, 50)}` });
  task('Checkpoint', 'done');

  emit('Building project');
  task('Build', 'running');
  active = await post(`/projects/${active.project_id}/build-all`, {});
  onProject?.(active);
  task('Build', 'done', `${Object.keys(active.files || {}).length} files`);

  emit('Starting preview');
  task('Preview', 'running');
  sandbox = await post(`/projects/${active.project_id}/sandbox/start`, {});
  onSandbox?.(sandbox);
  task('Preview', sandbox?.build_ok ? 'done' : 'blocked', sandbox?.build_ok ? 'Preview live' : 'Needs repair');

  task('Repair', sandbox?.build_ok ? 'done' : 'running');
  for (let round = 1; round <= maxRepairRounds && !sandbox?.build_ok; round += 1) {
    emit(`Repair round ${round}`);
    sandbox = await post(`/projects/${active.project_id}/sandbox/fix`, { instruction: goal.title });
    onSandbox?.(sandbox);
  }
  task('Repair', sandbox?.build_ok ? 'done' : 'blocked', sandbox?.build_ok ? 'Build repaired' : 'Still not green');

  emit('Validating project');
  task('Validate', 'running');
  active = await post(`/projects/${active.project_id}/validate`, {});
  onProject?.(active);
  task('Validate', active.status === 'valid' ? 'done' : 'blocked', active.status);

  const ok = Boolean(sandbox?.build_ok) || active.status === 'valid';
  emit(ok ? 'Execution complete' : 'Execution blocked');
  return { ok, project: active, sandbox };
}
