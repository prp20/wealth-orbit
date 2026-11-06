import { useQuery } from '@tanstack/react-query';
import { api } from '../../../api';

const pct = (value: unknown) => (value == null || value === '' ? '—' : `${Number(value).toFixed(2)}%`);

function signedPoints(current: unknown, previous: unknown): string {
  if (current == null || current === '' || previous == null || previous === '') return '—';
  const delta = Number(current) - Number(previous);
  if (Number.isNaN(delta)) return '—';
  return `${delta > 0 ? '+' : ''}${delta.toFixed(2)}`;
}

function signedCount(current: unknown, previous: unknown): string {
  if (current == null || current === '' || previous == null || previous === '') return '—';
  const delta = Number(current) - Number(previous);
  if (Number.isNaN(delta)) return '—';
  return `${delta > 0 ? '+' : ''}${delta}`;
}

const HOLDERS = [
  { key: 'promoter_pct', label: 'Promoter' },
  { key: 'fii_pct', label: 'FII' },
  { key: 'dii_pct', label: 'DII' },
  { key: 'government_pct', label: 'Government' },
  { key: 'public_pct', label: 'Public' },
] as const;

export default function ShareholdingPanel({ symbol }: { symbol: string }) {
  const shareholding = useQuery({
    queryKey: ['stock-shareholding', symbol],
    queryFn: () => api.stockShareholding(symbol),
  });
  const rows = [...(shareholding.data || [])]
    .sort((a: any, b: any) => String(a.period_end_date).localeCompare(String(b.period_end_date)))
    .slice(-8);

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Shareholding</h2>
          <p className="panel-subtitle">Ownership mix across recent reporting periods. Change is versus the previous row.</p>
        </div>
      </div>
      {shareholding.isLoading && <div className="loading">Loading shareholding…</div>}
      {shareholding.error && <div className="empty">{(shareholding.error as Error).message}</div>}
      {!shareholding.isLoading && !rows.length && (
        <div className="empty">No shareholding history yet. Update statements to load it.</div>
      )}
      {rows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Period</th>
                {HOLDERS.map((holder) => (
                  <th key={holder.key}>{holder.label}</th>
                ))}
                <th>Shareholders</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row: any, index: number) => {
                const previous = index > 0 ? rows[index - 1] : null;
                return (
                  <tr key={String(row.period_end_date)}>
                    <td>{String(row.period_end_date).slice(0, 10)}</td>
                    {HOLDERS.map((holder) => (
                      <td key={holder.key}>
                        {pct(row[holder.key])}
                        <small> {signedPoints(row[holder.key], previous?.[holder.key])}</small>
                      </td>
                    ))}
                    <td>
                      {row.shareholder_count ?? '—'}
                      <small> {signedCount(row.shareholder_count, previous?.shareholder_count)}</small>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
