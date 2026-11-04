import { useQuery } from '@tanstack/react-query';
import { api } from '../../../api';
import SyncJobButton from '../../../components/SyncJobButton';
import { formatDate, formatInr, formatPct, formatRatio } from '../../../lib/format';

const COLUMNS: { key: string; label: string; format: (value: unknown) => string }[] = [
  { key: 'metric_period', label: 'Period', format: (v) => String(v ?? '—') },
  { key: 'as_of_date', label: 'As of', format: formatDate },
  { key: 'current_nav', label: 'NAV', format: formatInr },
  { key: 'trailing_return', label: 'Trailing', format: formatPct },
  { key: 'cagr', label: 'CAGR', format: formatPct },
  { key: 'sharpe', label: 'Sharpe', format: formatRatio },
  { key: 'sortino', label: 'Sortino', format: formatRatio },
  { key: 'maximum_drawdown', label: 'Max DD', format: formatPct },
  { key: 'alpha', label: 'Alpha', format: formatRatio },
  { key: 'beta', label: 'Beta', format: formatRatio },
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
          <p className="panel-subtitle">Curated risk and return snapshots by period.</p>
        </div>
        <SyncJobButton
          entity="fund"
          id={schemeId}
          kind="metrics"
          invalidateKeys={[['fund-metrics', schemeId], ['fund', schemeId]]}
        />
      </div>
      {metrics.isLoading && <div className="loading">Loading performance…</div>}
      {metrics.error && <div className="empty">{(metrics.error as Error).message}</div>}
      {!metrics.isLoading && !rows.length && (
        <div className="empty">No metric snapshots yet. Sync metrics after NAV history is available.</div>
      )}
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
