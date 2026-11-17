export const HOME_INDEXES = ['NIFTY50', 'SENSEX', 'NIFTYBANK', 'NIFTYIT'];
export const SECTOR_INDEXES = ['NIFTYPHARMA', 'NIFTYAUTO', 'NIFTYFMCG', 'NIFTYMETAL'];
export const EXTRA_INDEXES_KEY = 'wealth-orbit:extra-home-indexes';
/** Home extras stay bounded; Indexes page loads the full server catalog. */
export const MAX_HOME_EXTRA_INDEXES = 8;
const INDEX_CODE_RE = /^[A-Z][A-Z0-9_]{1,31}$/;

export const INDEX_LABELS: Record<string, string> = {
  NIFTY50: 'Nifty 50',
  SENSEX: 'Sensex',
  NIFTYBANK: 'Nifty Bank',
  NIFTYIT: 'Nifty IT',
  NIFTY100: 'Nifty 100',
  NIFTY500: 'Nifty 500',
  NIFTYMIDCAP150: 'Nifty Midcap 150',
  NIFTYSMALLCAP250: 'Nifty Smallcap 250',
  NIFTYPHARMA: 'Nifty Pharma',
  NIFTYAUTO: 'Nifty Auto',
  NIFTYFMCG: 'Nifty FMCG',
  NIFTYMETAL: 'Nifty Metal',
};

export function readExtraIndexes(): string[] {
  try {
    const raw = window.localStorage.getItem(EXTRA_INDEXES_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map((item) => String(item || '').toUpperCase().replace(/[\s-]/g, ''))
      .filter((code) => INDEX_CODE_RE.test(code))
      .filter((code) => !HOME_INDEXES.includes(code))
      .slice(0, MAX_HOME_EXTRA_INDEXES);
  } catch {
    return [];
  }
}

export function rememberExtraIndex(code: string) {
  const normalized = String(code || '')
    .toUpperCase()
    .replace(/[\s-]/g, '');
  if (!INDEX_CODE_RE.test(normalized) || HOME_INDEXES.includes(normalized)) {
    return readExtraIndexes();
  }
  const next = Array.from(new Set([...readExtraIndexes(), normalized])).slice(0, MAX_HOME_EXTRA_INDEXES);
  window.localStorage.setItem(EXTRA_INDEXES_KEY, JSON.stringify(next));
  return next;
}

export function indexLabel(row: { index_code?: string; index_name?: string }) {
  const code = String(row.index_code || '').toUpperCase();
  return INDEX_LABELS[code] || row.index_name || row.index_code || 'Index';
}
