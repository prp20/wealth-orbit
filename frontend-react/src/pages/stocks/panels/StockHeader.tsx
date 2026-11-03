import { formatDate, formatInr } from '../../../lib/format';

export default function StockHeader({ stock }: { stock: any }) {
  const price = stock?.latest_price;
  const freshness = stock?.freshness || {};
  const badges = [
    { label: 'Price', value: freshness.latest_price_date },
    { label: 'Fundamentals', value: freshness.latest_fundamental_period_end },
    { label: 'Shareholding', value: freshness.latest_shareholding_period_end },
    { label: 'Technicals', value: freshness.latest_technical_calculated_at },
  ];

  return (
    <section className="stock-header panel">
      <div className="stock-header-main">
        <div>
          <p className="eyebrow">{stock?.trading_symbol || '—'}</p>
          <h1 className="stock-title">{stock?.company_name || stock?.trading_symbol || 'Stock'}</h1>
          <p className="subtitle">
            {[stock?.exchange, stock?.sector_name, stock?.industry_name].filter(Boolean).join(' · ') || '—'}
          </p>
        </div>
        <div className="stock-price-block">
          <small>Last close</small>
          <strong>{formatInr(price?.close)}</strong>
          <small>{formatDate(price?.date)}</small>
        </div>
      </div>
      <div className="freshness-badges">
        {badges.map((badge) => (
          <div key={badge.label} className={`freshness-badge ${badge.value ? 'fresh' : 'stale'}`}>
            <small>{badge.label}</small>
            <strong>{badge.value ? formatDate(badge.value) : 'Not synced'}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}
