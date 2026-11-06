import { useQuery } from '@tanstack/react-query';
import { api } from '../../../api';
import SyncJobButton from '../../../components/SyncJobButton';
import { formatCompactInr, formatDate, formatPercentPoints, formatRatio } from '../../../lib/format';

const ROWS: { key: string; label: string; format: (v: unknown) => string }[] = [
  { key: 'market_cap', label: 'Market cap', format: formatCompactInr },
  { key: 'enterprise_value', label: 'Enterprise value', format: formatCompactInr },
  { key: 'stock_pe', label: 'P/E (trailing)', format: formatRatio },
  { key: 'price_to_book', label: 'P/B', format: formatRatio },
  { key: 'ev_ebitda', label: 'EV / EBITDA', format: formatRatio },
  { key: 'ev_sales', label: 'EV / Sales', format: formatRatio },
  { key: 'dividend_yield', label: 'Dividend yield', format: formatPercentPoints },
  { key: 'fcf_yield', label: 'FCF yield', format: formatPercentPoints },
  { key: 'ebitda_ttm', label: 'EBITDA (TTM)', format: formatCompactInr },
  { key: 'net_debt', label: 'Net debt', format: formatCompactInr },
];

export default function ValuationPanel({ symbol }: { symbol: string }) {
  const valuation = useQuery({
    queryKey: ['stock-valuation', symbol],
    queryFn: () => api.stockValuation(symbol),
  });
  const data = valuation.data;
  const metrics = data?.metrics || {};

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Valuation</h2>
          <p className="panel-subtitle">
            Trailing multiples with as-of context. Forward estimates are not shown without a licensed
            source.
          </p>
        </div>
        <SyncJobButton
          symbol={symbol}
          kind="daily_metrics"
          label="Update ratios"
          invalidateKeys={[['stock-valuation', symbol], ['stock', symbol], ['stock-daily-metrics', symbol]]}
        />
      </div>
      {valuation.isLoading && <div className="loading">Loading valuation…</div>}
      {valuation.error && <div className="empty">{(valuation.error as Error).message}</div>}
      {data && (
        <>
          <p className="panel-subtitle">
            As of {formatDate(data.as_of) || '—'} · Source {data.source || '—'}
            {data.forward_estimates_available ? '' : ' · Forward PE unavailable'}
          </p>
          <div className="metrics compact-metrics snapshot-metrics">
            {ROWS.map((row) => (
              <div className="metric" key={row.key}>
                <small>{row.label}</small>
                <strong>{row.format(metrics[row.key])}</strong>
              </div>
            ))}
          </div>
          <ul className="panel-notes">
            {(data.notes || []).map((note: string) => (
              <li key={note}>{note}</li>
            ))}
            <li>PEG is omitted until it is trailing earnings growth from stored results.</li>
          </ul>
        </>
      )}
    </section>
  );
}
