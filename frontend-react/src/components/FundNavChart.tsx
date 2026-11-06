import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import { ChartRange, rangeToFromDate } from './ChartToolbar';
import MarketChart from './MarketChart';

type Props = {
  schemeId: string;
  range: ChartRange;
  overlay: boolean;
  benchmarkAvailable: boolean;
};

function toDateKey(value: unknown): string {
  return String(value ?? '').slice(0, 10);
}

function normalizeSeries(
  fundRows: any[],
  benchRows: any[],
): { dates: string[]; fund: number[]; bench: number[] } | null {
  const fundByDate = new Map<string, number>();
  for (const row of fundRows) {
    const key = toDateKey(row.date);
    const nav = Number(row.nav);
    if (key && Number.isFinite(nav) && nav > 0) fundByDate.set(key, nav);
  }
  const benchByDate = new Map<string, number>();
  for (const row of benchRows) {
    const key = toDateKey(row.date);
    const close = Number(row.close);
    if (key && Number.isFinite(close) && close > 0) benchByDate.set(key, close);
  }
  const dates = [...fundByDate.keys()].filter((date) => benchByDate.has(date)).sort();
  if (dates.length < 2) return null;
  const fundBase = fundByDate.get(dates[0])!;
  const benchBase = benchByDate.get(dates[0])!;
  return {
    dates,
    fund: dates.map((date) => (fundByDate.get(date)! / fundBase) * 100),
    bench: dates.map((date) => (benchByDate.get(date)! / benchBase) * 100),
  };
}

export default function FundNavChart({ schemeId, range, overlay, benchmarkAvailable }: Props) {
  const fromDate = rangeToFromDate(range);
  const fundHistory = useQuery({
    queryKey: ['history', 'fund', schemeId, range],
    queryFn: () => api.fundHistory(schemeId, fromDate || '', ''),
  });
  const benchHistory = useQuery({
    queryKey: ['fund-benchmark-history', schemeId, range],
    queryFn: () => api.fundBenchmarkHistory(schemeId, fromDate || '', ''),
    enabled: overlay && benchmarkAvailable,
  });

  if (!overlay || !benchmarkAvailable) {
    return <MarketChart kind="fund" id={schemeId} bare range={range} />;
  }

  if (fundHistory.isLoading || benchHistory.isLoading) {
    return <div className="empty">Loading chart…</div>;
  }

  const series = normalizeSeries(fundHistory.data || [], benchHistory.data || []);
  if (!series) {
    return (
      <div className="chart-plot">
        <div className="empty">
          Benchmark history is not aligned yet. Turn the overlay off.
        </div>
        <MarketChart kind="fund" id={schemeId} bare range={range} />
      </div>
    );
  }

  const all = [...series.fund, ...series.bench];
  const min = Math.min(...all);
  const max = Math.max(...all);
  const span = max - min || 1;
  const toPoints = (values: number[]) =>
    values
      .map((value, index) => `${(index / (values.length - 1 || 1)) * 100},${100 - ((value - min) / span) * 100}`)
      .join(' ');

  return (
    <div className="chart-plot fund-overlay-chart">
      <div className="overlay-legend">
        <span className="overlay-legend-fund">Fund (normalized)</span>
        <span className="overlay-legend-bench">Benchmark (normalized)</span>
      </div>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="line-chart">
        <polyline
          points={toPoints(series.fund)}
          fill="none"
          stroke="#42a87c"
          strokeWidth="1.5"
          vectorEffect="non-scaling-stroke"
        />
        <polyline
          points={toPoints(series.bench)}
          fill="none"
          stroke="#64748b"
          strokeWidth="1.5"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <small className="chart-caption">
        {series.dates[0]} to {series.dates[series.dates.length - 1]} · {series.dates.length} common points ·
        indexed to 100
      </small>
    </div>
  );
}
