import SyncJobButton from '../../../components/SyncJobButton';
import { formatCompactInr, formatInr, formatPct, formatRatio } from '../../../lib/format';

export default function KeyMetricsPanel({ schemeId, fund }: { schemeId: string; fund: any }) {
  const metrics = fund?.latest_metrics;
  const enrichment = fund?.latest_enrichment;
  const nav = fund?.latest_nav?.nav ?? metrics?.current_nav;
  const returnValue = metrics?.cagr ?? metrics?.trailing_return;

  return (
    <section className="panel key-ratios-panel">
      <div className="panel-heading">
        <div>
          <h2>Key metrics</h2>
          <p className="panel-subtitle">
            Latest snapshot. Alpha/Beta need Benchmark history + Metrics sync; AUM/Expense need Enrichment
            sync.
          </p>
        </div>
        <SyncJobButton
          entity="fund"
          id={schemeId}
          kind="metrics"
          invalidateKeys={[['fund-metrics', schemeId], ['fund', schemeId], ['fund-similar', schemeId]]}
        />
      </div>
      <section className="metrics compact-metrics snapshot-metrics fund-key-metrics">
        <div className="metric">
          <small>NAV</small>
          <strong>{formatInr(nav)}</strong>
        </div>
        <div className="metric">
          <small>{metrics?.cagr != null ? 'CAGR' : 'Trailing'}</small>
          <strong>{formatPct(returnValue)}</strong>
        </div>
        <div className="metric">
          <small>Sharpe</small>
          <strong>{formatRatio(metrics?.sharpe)}</strong>
        </div>
        <div className="metric">
          <small>Alpha</small>
          <strong>{formatRatio(metrics?.alpha)}</strong>
        </div>
        <div className="metric">
          <small>Beta</small>
          <strong>{formatRatio(metrics?.beta)}</strong>
        </div>
        <div className="metric">
          <small>AUM</small>
          <strong>{formatCompactInr(enrichment?.aum)}</strong>
        </div>
        <div className="metric">
          <small>Expense</small>
          <strong>{formatPct(enrichment?.expense_ratio)}</strong>
        </div>
      </section>
    </section>
  );
}
