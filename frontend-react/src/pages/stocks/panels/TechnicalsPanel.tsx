import { useQuery } from '@tanstack/react-query';
import { api, StockTechnicalIndicatorsPayload } from '../../../api';
import InfoTip from '../../../components/InfoTip';
import SyncJobButton from '../../../components/SyncJobButton';
import { formatDate, formatRatio } from '../../../lib/format';

const FAMILIES: { title: string; match: (code: string) => boolean }[] = [
  { title: 'RSI', match: (code) => code.startsWith('RSI') },
  { title: 'SMA', match: (code) => code.startsWith('SMA') },
  { title: 'EMA', match: (code) => code.startsWith('EMA') },
  { title: 'Stochastic', match: (code) => code.startsWith('STOCH') },
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
  const payload: StockTechnicalIndicatorsPayload | undefined = technical.data;
  const rows = payload?.records || [];
  const syncError = payload?.sync_error || null;
  const latest = latestBySeries(rows);

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <div className="fundamentals-title-row">
            <h2>Technicals</h2>
            <InfoTip label="About technical indicators">
              <p>
                Values come from the latest stored OHLCV snapshot only (SMA 20/50/200, EMA 20/50,
                RSI, MACD, Bollinger, ATR, Stochastic). Missing data stays empty — we do not compute
                ephemeral values on read.
              </p>
              <p>
                These are <strong>research metrics</strong> for screening and review, not investment
                advice or trade signals.
              </p>
              <p>Interactive chart overlays and drawings are out of scope (planned for a later release).</p>
            </InfoTip>
          </div>
          <p className="panel-subtitle">
            Research metrics from stored indicators for the latest trading day — not advice. Chart overlays
            are out of scope.
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
      {!technical.isLoading && !technical.error && !latest.length && (
        <div className="empty">
          No stored technical indicators yet. Sync prices first, then refresh this panel.
          {syncError ? ` (${syncError})` : ''}
        </div>
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