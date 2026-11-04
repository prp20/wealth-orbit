import { useQuery } from '@tanstack/react-query';
import { api } from '../../../api';
import SyncJobButton from '../../../components/SyncJobButton';
import { formatDate, formatPct } from '../../../lib/format';

export default function ManagersPanel({ schemeId }: { schemeId: string }) {
  const managers = useQuery({
    queryKey: ['fund-managers', schemeId],
    queryFn: () => api.fundManagers(schemeId),
  });
  const data = managers.data;
  const rows = data?.assignments || [];

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Fund managers</h2>
          <p className="panel-subtitle">
            Assignment history with tenure-adjusted scheme NAV return. Do not attribute full-scheme history to a
            manager who only covered part of the period.
          </p>
        </div>
        <SyncJobButton
          entity="fund"
          id={schemeId}
          kind="managers"
          invalidateKeys={[['fund-managers', schemeId]]}
        />
      </div>
      {managers.isLoading && <div className="loading">Loading managers…</div>}
      {managers.error && <div className="empty">{(managers.error as Error).message}</div>}
      {data && data.available === false && <div className="empty">{data.reason || 'No managers yet.'}</div>}
      {rows.length > 0 && (
        <div className="table-wrap">
          <table className="stock-table">
            <thead>
              <tr>
                <th>Manager</th>
                <th>Start</th>
                <th>End</th>
                <th>Current</th>
                <th>Tenure return</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row: any) => (
                <tr key={`${row.manager_name}-${row.start_date}`}>
                  <td className="company-cell">{row.manager_name}</td>
                  <td>{formatDate(row.start_date)}</td>
                  <td>{formatDate(row.end_date)}</td>
                  <td>{row.is_current ? 'Yes' : 'No'}</td>
                  <td>{formatPct(row.tenure_absolute_return)}</td>
                  <td>{row.source_name || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
