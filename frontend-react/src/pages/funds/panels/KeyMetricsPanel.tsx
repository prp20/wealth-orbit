import { formatCompactInr, formatDisplayDate, formatInr, formatPct } from '../../../lib/format';
import { periodReturnLabel, periodReturnValue } from '../../../lib/fundMetrics';

export default function KeyMetricsPanel({ fund }: { schemeId: string; fund: any }) {
  const metrics = fund?.latest_metrics;
  const enrichment = fund?.latest_enrichment;
  const nav = fund?.latest_nav;
  const navValue = nav?.nav ?? metrics?.current_nav;
  const navDate = nav?.date;

  return (
    <section className="panel key-ratios-panel">
      <div className="panel-heading">
        <h2>Key metrics</h2>
      </div>
      <section className="metrics compact-metrics snapshot-metrics fund-key-metrics">
        <div className="metric">
          <small>{navDate ? `NAV · ${formatDisplayDate(navDate)}` : 'NAV'}</small>
          <strong>{formatInr(navValue)}</strong>
        </div>
        <div className="metric">
          <small>{periodReturnLabel(metrics?.metric_period)}</small>
          <strong>{formatPct(periodReturnValue(metrics))}</strong>
        </div>
        <div className="metric">
          <small>Expense</small>
          <strong>{formatPct(enrichment?.expense_ratio)}</strong>
        </div>
        <div className="metric">
          <small>AUM</small>
          <strong>{formatCompactInr(enrichment?.aum)}</strong>
        </div>
        <div className="metric">
          <small>Max drawdown, full history</small>
          <strong>{formatPct(metrics?.maximum_drawdown)}</strong>
        </div>
      </section>
    </section>
  );
}
