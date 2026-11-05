export type RecentItem = {
  kind: 'fund' | 'stock';
  id: string;
  label: string;
  path: string;
  viewedAt: string;
};

const KEY = 'wealth-orbit.recent';

export function readRecent(): RecentItem[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((row) => row && (row.kind === 'fund' || row.kind === 'stock') && row.id && row.path)
      .slice(0, 8);
  } catch {
    return [];
  }
}

export function recordRecent(item: Omit<RecentItem, 'viewedAt'>) {
  try {
    const next = [
      { ...item, viewedAt: new Date().toISOString() },
      ...readRecent().filter((row) => !(row.kind === item.kind && row.id === item.id)),
    ].slice(0, 8);
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* private mode or a full quota should not break the detail page */
  }
}
