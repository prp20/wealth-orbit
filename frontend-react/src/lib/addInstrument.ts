export type InstrumentKind = 'stock' | 'fund' | 'index';

export type HistoryPeriod = '5y' | '10y' | 'max';

export const HISTORY_PERIOD_OPTIONS: { value: HistoryPeriod; label: string }[] = [
  { value: '5y', label: '5 years' },
  { value: '10y', label: '10 years' },
  { value: 'max', label: 'Maximum available' },
];

export const DEFAULT_HISTORY_PERIOD: HistoryPeriod = '10y';

export function addInstrumentCodeLabel(kind: InstrumentKind): string {
  if (kind === 'stock') return 'NSE trading symbol';
  if (kind === 'fund') return 'AMFI scheme code';
  return 'Index code';
}

export function addInstrumentButtonLabel(kind: InstrumentKind): string {
  if (kind === 'stock') return 'Add stock';
  if (kind === 'fund') return 'Add fund';
  return 'Add index';
}

export function addInstrumentDialogTitle(kind: InstrumentKind): string {
  if (kind === 'stock') return 'Add stock';
  if (kind === 'fund') return 'Add fund';
  return 'Add index';
}

export function validateAddInstrumentCode(code: string, action: 'preview' | 'add'): string | null {
  if (code.trim()) return null;
  return action === 'preview' ? 'Enter a code to preview.' : 'Enter a code to add.';
}

export function stockDetailPath(symbol: string): string {
  return `/stocks/${encodeURIComponent(symbol)}`;
}

export function fundDetailPath(schemeCode: string): string {
  return `/mutualfunds/${encodeURIComponent(schemeCode)}`;
}

export function normalizeHistoryPeriod(value: string | null | undefined): HistoryPeriod {
  if (value === '10y' || value === 'max' || value === '5y') return value;
  return DEFAULT_HISTORY_PERIOD;
}
