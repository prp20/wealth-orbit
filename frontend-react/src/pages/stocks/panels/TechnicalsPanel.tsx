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

function latestBySeries(rows: any[]) {
  const map = new Map<string, any>();
  for (const row of rows) {
    const key = `${row.indicator_code}|${row.indicator_period || ''}|${row.component || ''}`;
    const existing = map.get(key);
    if (!existing || String(row.date) >= String(existing.date)) map.set(key, row);
  }
  return Array.from(map.values()).sort((a, b) =>
    String(a.indicator_code).localeCompare(String(b.indicator_code)),
  );
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
            Core indicators (SMA/EMA, RSI, MACD, Bollinger, ATR) derived from stored OHLCV. Source:
            derived.
          </p>
        </div>
        <SyncJobButton
          symbol={symbol}
          kind="technical"
          invalidateKeys={[['stock-technical', symbol]]}
        />
      </div>
      {technical.isLoading && <div className="loading">Loading technicals…</div>}
      {technical.error && <div className="empty">{(technical.error as Error).message}</div>}
      {!technical.isLoading && !latest.length && (
        <div className="empty">No technical indicators yet. Sync technicals after prices are available.</div>
      )}
      {FAMILIES.map((family) => {
        const items = latest.filter((row) => family.match(String(row.indicator_code || '').toUpperCase()));
        if (!items.length) return null;
        return (
          <div key={family.title} className="technical-family">
            <h3>{family.title}</h3>
            <div className="metrics compact-metrics">
              {items.map((row) => (
                <div className="metric" key={`${row.indicator_code}-${row.indicator_period}-${row.component}`}>
                  <small>
                    {row.indicator_code}
                    {row.indicator_period ? ` (${row.indicator_period})` : ''}
                    {row.component ? ` · ${row.component}` : ''}
                  </small>
                  <strong>{formatRatio(row.indicator_value)}</strong>
                  <small>{formatDate(row.date)}</small>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </section>
  );
}
