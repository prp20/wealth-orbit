export const METRIC_PERIODS = ['1M', '3M', '6M', '1Y', '3Y', '5Y', '10Y'] as const;
export type MetricPeriod = (typeof METRIC_PERIODS)[number];

export const SHORT_METRIC_PERIODS = new Set<string>(['1M', '3M', '6M']);

export const SCREEN_SORT_OPTIONS = [
  { value: 'scheme_name', label: 'Name' },
  { value: 'trailing_return', label: 'Trailing return' },
  { value: 'cagr', label: 'CAGR' },
  { value: 'sharpe', label: 'Sharpe, full history' },
  { value: 'maximum_drawdown', label: 'Max drawdown, full history' },
  { value: 'aum', label: 'AUM' },
  { value: 'expense_ratio', label: 'Expense' },
] as const;

const PERIOD_RETURN: Record<string, { field: 'trailing' | 'cagr'; label: string }> = {
  '1M': { field: 'trailing', label: '1-month return' },
  '3M': { field: 'trailing', label: '3-month return' },
  '6M': { field: 'trailing', label: '6-month return' },
  '1Y': { field: 'trailing', label: '1-year return' },
  '3Y': { field: 'cagr', label: '3-year CAGR' },
  '5Y': { field: 'cagr', label: '5-year CAGR' },
  '10Y': { field: 'cagr', label: '10-year CAGR' },
};

const PLAN_LABELS: Record<string, string> = {
  DIRECT: 'Direct',
  REGULAR: 'Regular',
  GROWTH: 'Growth',
  IDCW: 'IDCW',
  BONUS: 'Bonus',
};

export function periodReturnLabel(period: unknown): string {
  return PERIOD_RETURN[String(period || '').toUpperCase()]?.label || 'Return';
}

export function periodReturnValue(metrics: {
  metric_period?: unknown;
  trailing_return?: unknown;
  cagr?: unknown;
} | null | undefined): unknown {
  if (!metrics) return null;
  const spec = PERIOD_RETURN[String(metrics.metric_period || '').toUpperCase()];
  if (!spec) return metrics.cagr ?? metrics.trailing_return;
  return spec.field === 'cagr' ? metrics.cagr : metrics.trailing_return;
}

export function planOptionLabel(value: unknown): string {
  const text = String(value || '').trim();
  if (!text) return '';
  const known = PLAN_LABELS[text.toUpperCase()];
  if (known) return known;
  return text.toLowerCase().replace(/\b\w/g, (char) => char.toUpperCase());
}
