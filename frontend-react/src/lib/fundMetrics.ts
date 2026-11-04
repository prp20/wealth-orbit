export const METRIC_PERIODS = ['1M', '3M', '6M', '1Y', '3Y', '5Y', '10Y'] as const;
export type MetricPeriod = (typeof METRIC_PERIODS)[number];

export const SHORT_METRIC_PERIODS = new Set<string>(['1M', '3M', '6M']);

export const SCREEN_SORT_OPTIONS = [
  { value: 'scheme_name', label: 'Name' },
  { value: 'trailing_return', label: 'Trailing return' },
  { value: 'cagr', label: 'CAGR' },
  { value: 'sharpe', label: 'Sharpe' },
  { value: 'maximum_drawdown', label: 'Max drawdown' },
  { value: 'aum', label: 'AUM' },
  { value: 'expense_ratio', label: 'Expense' },
] as const;
