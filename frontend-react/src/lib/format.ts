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
