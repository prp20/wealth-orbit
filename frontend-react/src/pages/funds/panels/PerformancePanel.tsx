import { useQuery } from '@tanstack/react-query';
import { api } from '../../../api';
import { formatDate, formatInr, formatPct } from '../../../lib/format';

const COLUMNS: { key: string; label: string; format: (value: unknown) => string }[] = [
  { key: 'metric_period', label: 'Period', format: (v) => String(v ?? '—') },
  { key: 'as_of_date', label: 'As of', format: (v) => formatDate(v) },
  { key: 'current_nav', label: 'NAV', format: (v) => formatInr(v) },
  { key: 'trailing_return', label: 'Trailing', format: (v) => formatPct(v) },
  { key: 'cagr', label: 'CAGR', format: (v) => formatPct(v) },
  { key: 'rolling_latest', label: 'Rolling latest', format: (v) => formatPct(v) },
  { key: 'rolling_median', label: 'Rolling median', format: (v) => formatPct(v) },
  { key: 'rolling_min', label: 'Rolling min', format: (v) => formatPct(v) },
  { key: 'rolling_max', label: 'Rolling max', format: (v) => formatPct(v) },
];

export default function PerformancePanel({ schemeId }: { schemeId: string }) {
  const metrics = useQuery({
    queryKey: ['fund-metrics', schemeId],
    queryFn: () => api.fundMetrics(schemeId),
  });
  const rows = Array.isArray(metrics.data) ? metrics.data : metrics.data ? [metrics.data] : [];

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Performance</h2>
          <p className="panel-subtitle">Trailing return, CAGR, and rolling windows by period.</p>
        </div>
      </div>
      {metrics.isLoading && <div className="loading">Loading performance…</div>}
      {metrics.error && <div className="empty">{(metrics.error as Error).message}</div>}
      {!metrics.isLoading && !rows.length && <div className="empty">No returns for this fund yet.</div>}
      {rows.length > 0 && (
        <div className="table-wrap">
          <table className="stock-table">
            <thead>
              <tr>
                {COLUMNS.map((column) => (
                  <th key={column.key}>{column.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row: any, index: number) => (
                <tr key={`${row.metric_period}-${row.as_of_date}-${index}`}>
                  {COLUMNS.map((column) => (
                    <td key={column.key}>{column.format(row[column.key])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
