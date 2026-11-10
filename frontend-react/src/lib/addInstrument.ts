export type InstrumentKind = 'stock' | 'fund' | 'index';

export function addInstrumentCodeLabel(kind: InstrumentKind): string {
  if (kind === 'stock') return 'NSE trading symbol';
  if (kind === 'fund') return 'AMFI scheme code';
  return 'Index code';
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
