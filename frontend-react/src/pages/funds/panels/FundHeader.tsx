import { formatDate, formatInr } from '../../../lib/format';

export default function FundHeader({ fund }: { fund: any }) {
  const nav = fund?.latest_nav;
  const freshness = fund?.freshness || {};
  const badges = [
    { label: 'NAV', value: freshness.latest_nav_date },
    { label: 'Metrics', value: freshness.latest_metrics_as_of },
    { label: 'Enrichment', value: freshness.latest_enrichment_as_of },
    { label: 'Benchmark', value: freshness.latest_benchmark_history_date },
  ];

  return (
    <section className="stock-header panel">
      <div className="stock-header-main">
        <div>
          <p className="eyebrow">{fund?.scheme_code || '—'}</p>
          <h1 className="stock-title">{fund?.scheme_name || fund?.scheme_code || 'Fund'}</h1>
          <p className="subtitle">
            {[fund?.amc_name, fund?.category_name, fund?.subcategory_name].filter(Boolean).join(' · ') || '—'}
          </p>
        </div>
        <div className="stock-price-block">
          <small>Last NAV</small>
          <strong>{formatInr(nav?.nav)}</strong>
          <small>{formatDate(nav?.date)}</small>
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
