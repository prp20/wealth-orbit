import { formatDisplayDate } from './format';

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

export function clearRecent() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* private mode should not break logout */
  }
}

export function formatRecentWhen(viewedAt: string, now = new Date()): string {
  const viewed = new Date(viewedAt);
  if (Number.isNaN(viewed.getTime())) return '';
  const start = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  const days = Math.round((start(now) - start(viewed)) / 86400000);
  if (days <= 0) return 'Today';
  if (days === 1) return 'Yesterday';
  const month = String(viewed.getMonth() + 1).padStart(2, '0');
  const day = String(viewed.getDate()).padStart(2, '0');
  return formatDisplayDate(`${viewed.getFullYear()}-${month}-${day}`);
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
