const empty = (value: unknown) => value == null || value === '';

export function formatInr(value: unknown, digits = 2): string {
  if (empty(value)) return '—';
  const amount = Number(value);
  if (Number.isNaN(amount)) return '—';
  return `₹${new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(amount)}`;
}

/** Compact Indian market-cap style: Cr / L / plain INR. */
export function formatCompactInr(value: unknown): string {
  if (empty(value)) return '—';
  const amount = Number(value);
  if (Number.isNaN(amount)) return '—';
  const abs = Math.abs(amount);
  if (abs >= 1e7) {
    return `₹${new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(amount / 1e7)} Cr`;
  }
  if (abs >= 1e5) {
    return `₹${new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(amount / 1e5)} L`;
  }
  return formatInr(amount, 0);
}

export function formatRatio(value: unknown, digits = 2): string {
  if (empty(value)) return '—';
  const amount = Number(value);
  if (Number.isNaN(amount)) return '—';
  return new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(amount);
}

/** Percent points already stored as 1.2 → 1.20%. Does not rescale fractions. */
export function formatPercentPoints(value: unknown, digits = 2): string {
  if (empty(value)) return '—';
  const amount = Number(value);
  if (Number.isNaN(amount)) return '—';
  return `${new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(amount)}%`;
}

/** Screener statement amounts are already in crore. Do not divide by 1e7. */
export function formatCrore(value: unknown): string {
  if (empty(value)) return '—';
  const amount = Number(value);
  if (Number.isNaN(amount)) return '—';
  return `${new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(amount)} Cr`;
}

export function formatCount(value: unknown): string {
  if (empty(value)) return '—';
  const amount = Number(value);
  if (Number.isNaN(amount)) return '—';
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(amount);
}

const PERCENT_POINT_CODES = new Set([
  'OPERATING_MARGIN',
  'TAX_RATE',
  'ROE',
  'ROCE',
  'ROA',
  'PAT_MARGIN',
  'REVENUE_GROWTH',
  'EPS_GROWTH',
]);

const RATIO_CODES = new Set([
  'DEBT_TO_EQUITY',
  'INTEREST_COVERAGE',
  'CURRENT_RATIO',
  'QUICK_RATIO',
  'ASSET_TURNOVER',
]);

export function formatStatementValue(code: string, value: unknown): string {
  if (code === 'EPS') return formatInr(value);
  if (PERCENT_POINT_CODES.has(code)) return formatPercentPoints(value);
  if (RATIO_CODES.has(code)) return formatRatio(value);
  return formatCrore(value);
}

/** First sentence, capped at 280 characters. */
export function firstSentence(value: unknown, limit = 280): string {
  if (empty(value)) return '';
  const text = String(value).trim();
  if (!text) return '';
  const mark = /[.!?]/.exec(text);
  const piece = mark ? text.slice(0, mark.index + 1).trim() : text;
  if (piece.length <= limit) return piece;
  const cut = piece.slice(0, limit);
  const space = cut.lastIndexOf(' ');
  const clipped = (space > 0 ? cut.slice(0, space) : cut).trimEnd();
  return `${clipped}…`;
}

/** Treat values as already-percent (e.g. 12.5 → 12.50%) or as fractions if |x| ≤ 1.5. */
export function formatPct(value: unknown, digits = 2): string {
  if (empty(value)) return '—';
  let amount = Number(value);
  if (Number.isNaN(amount)) return '—';
  if (Math.abs(amount) > 0 && Math.abs(amount) <= 1.5) amount *= 100;
  return `${new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(amount)}%`;
}

export function formatDate(value: unknown): string {
  if (empty(value)) return '—';
  return String(value).slice(0, 10);
}

const DISPLAY_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** Calendar date without a timezone shift: 2026-11-05 → 5 Nov 2026. */
export function formatDisplayDate(value: unknown): string {
  if (empty(value)) return '—';
  const text = String(value).slice(0, 10);
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text);
  if (!match) return text;
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (month < 1 || month > 12 || day < 1 || day > 31) return text;
  return `${day} ${DISPLAY_MONTHS[month - 1]} ${match[1]}`;
}
