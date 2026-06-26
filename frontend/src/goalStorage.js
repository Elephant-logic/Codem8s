export const STORAGE_KEY = 'codem8s-goals-v1';

export function readItems() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
  } catch {
    return [];
  }
}

export function writeItems(items) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, 20)));
}
