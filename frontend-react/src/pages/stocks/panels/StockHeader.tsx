import { formatDate, formatInr } from '../../../lib/format';

export default function StockHeader({ stock }: { stock: any }) {
  const price = stock?.latest_price;
  const freshness = stock?.freshness || {};
  const sources = stock?.data_sources || {};
  const badges = [
    { label: 'Price', value: freshness.latest_price_date },
    { label: 'Fundamentals', value: freshness.latest_fundamental_period_end },
    { label: 'Shareholding', value: freshness.latest_shareholding_period_end },
    { label: 'Technicals', value: freshness.latest_technical_calculated_at },
  ];
  const identityBits = [
    stock?.exchange,
    stock?.sector_name,
    stock?.industry_name,
    stock?.isin ? `ISIN ${stock.isin}` : null,
    stock?.bse_code ? `BSE ${stock.bse_code}` : null,
    stock?.market_cap_class || null,
    stock?.listing_status || null,
  ].filter(Boolean);

  return (
    <section className="stock-header panel">
      <div className="stock-header-main">
        <div>
          <p className="eyebrow">{stock?.trading_symbol || '—'}</p>
          <h1 className="stock-title">{stock?.company_name || stock?.trading_symbol || 'Stock'}</h1>
          <p className="subtitle">{identityBits.join(' · ') || '—'}</p>
          {!stock?.adjusted_history_available && (
            <p className="panel-subtitle">
              Corporate-action-adjusted history unavailable until a licensed CA feed is configured.
              Prices source: {sources.prices || 'yfinance'}.
            </p>
          )}
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
