import { useQuery } from '@tanstack/react-query';
import { api } from '../../../api';
import SyncJobButton from '../../../components/SyncJobButton';
import { formatDate, formatRatio } from '../../../lib/format';

const FAMILIES: { title: string; match: (code: string) => boolean }[] = [
  { title: 'RSI', match: (code) => code.startsWith('RSI') },
  { title: 'SMA / EMA', match: (code) => code.startsWith('SMA') || code.startsWith('EMA') },
  { title: 'MACD', match: (code) => code.startsWith('MACD') },
  { title: 'Bollinger', match: (code) => code.startsWith('BB') || code.includes('BOLL') },
  { title: 'ATR', match: (code) => code.startsWith('ATR') },
];

function familyFor(code: string) {
  const upper = String(code || '').toUpperCase();
  return FAMILIES.find((family) => family.match(upper))?.title || 'Other';
}

function latestBySeries(rows: any[]) {
  const map = new Map<string, any>();
  for (const row of rows) {
    const key = `${row.indicator_code}|${row.indicator_period || ''}|${row.component || ''}`;
    const existing = map.get(key);
    if (!existing || String(row.date) >= String(existing.date)) map.set(key, row);
  }
  const familyOrder = new Map(FAMILIES.map((family, index) => [family.title, index]));
  return Array.from(map.values()).sort((a, b) => {
    const fa = familyFor(a.indicator_code);
    const fb = familyFor(b.indicator_code);
    const familyCmp = (familyOrder.get(fa) ?? 99) - (familyOrder.get(fb) ?? 99);
    if (familyCmp !== 0) return familyCmp;
    const codeCmp = String(a.indicator_code).localeCompare(String(b.indicator_code));
    if (codeCmp !== 0) return codeCmp;
    return String(a.component || '').localeCompare(String(b.component || ''));
  });
}

export default function TechnicalsPanel({ symbol }: { symbol: string }) {
  const technical = useQuery({
    queryKey: ['stock-technical', symbol],
    queryFn: () => api.stockTechnical(symbol),
  });
  const rows = technical.data || [];
  const latest = latestBySeries(rows);

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Technicals</h2>
          <p className="panel-subtitle">
            Core indicators (SMA/EMA, RSI, MACD, Bollinger, ATR) computed from OHLCV and stored for
            the latest trading day only.
          </p>
        </div>
        <SyncJobButton
          symbol={symbol}
          kind="technical"
          label="Refresh indicators"
          invalidateKeys={[['stock-technical', symbol]]}
        />
      </div>
      {technical.isLoading && <div className="loading">Loading technicals…</div>}
      {technical.error && <div className="empty">{(technical.error as Error).message}</div>}
      {!technical.isLoading && !latest.length && (
        <div className="empty">No technicals yet. Sync prices first, then refresh this panel.</div>
      )}
      {latest.length > 0 && (
        <div className="table-wrap">
          <table className="stock-table">
            <thead>
              <tr>
                <th>Family</th>
                <th>Indicator</th>
                <th>Period</th>
                <th>Component</th>
                <th>Value</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {latest.map((row) => (
                <tr key={`${row.indicator_code}-${row.indicator_period}-${row.component}`}>
                  <td>{familyFor(row.indicator_code)}</td>
                  <td>{row.indicator_code}</td>
                  <td>{row.indicator_period || '—'}</td>
                  <td>{row.component || '—'}</td>
                  <td>{formatRatio(row.indicator_value)}</td>
                  <td>{formatDate(row.date)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
