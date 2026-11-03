import { useQuery } from '@tanstack/react-query';
import { api } from '../../../api';
import SyncJobButton from '../../../components/SyncJobButton';

const pct = (value: unknown) => (value == null || value === '' ? '—' : `${Number(value).toFixed(2)}%`);

export default function ShareholdingPanel({ symbol }: { symbol: string }) {
  const shareholding = useQuery({
    queryKey: ['stock-shareholding', symbol],
    queryFn: () => api.stockShareholding(symbol),
  });
  const rows = [...(shareholding.data || [])].reverse().slice(-8);

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Shareholding</h2>
          <p className="panel-subtitle">Ownership mix across recent reporting periods.</p>
        </div>
        <SyncJobButton
          symbol={symbol}
          kind="shareholding"
          invalidateKeys={[['stock-shareholding', symbol], ['stock-fundamentals-summary', symbol]]}
        />
      </div>
      {shareholding.isLoading && <div className="loading">Loading shareholding…</div>}
      {shareholding.error && <div className="empty">{(shareholding.error as Error).message}</div>}
      {!shareholding.isLoading && !rows.length && (
        <div className="empty">No shareholding history yet. Sync fundamentals/shareholding to load it.</div>
      )}
      {rows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Period</th>
                <th>Promoter</th>
                <th>FII</th>
                <th>DII</th>
                <th>Government</th>
                <th>Public</th>
                <th>Shareholders</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row: any) => (
                <tr key={String(row.period_end_date)}>
                  <td>{String(row.period_end_date).slice(0, 10)}</td>
                  <td>{pct(row.promoter_pct)}</td>
                  <td>{pct(row.fii_pct)}</td>
                  <td>{pct(row.dii_pct)}</td>
                  <td>{pct(row.government_pct)}</td>
                  <td>{pct(row.public_pct)}</td>
                  <td>{row.shareholder_count ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
