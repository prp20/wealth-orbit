import SyncJobButton from '../../../components/SyncJobButton';
import { formatPct, formatRatio } from '../../../lib/format';

export default function RiskPanel({ schemeId, fund }: { schemeId: string; fund: any }) {
  const metrics = fund?.latest_metrics;

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Risk</h2>
          <p className="panel-subtitle">
            Risk columns use daily returns over full available NAV history (annualized with √252). Risk-free
            rate and calculation version come from the latest metrics snapshot. Short periods (1M/3M/6M)
            store trailing return only — they do not change these risk tiles.
          </p>
        </div>
        <SyncJobButton
          entity="fund"
          id={schemeId}
          kind="metrics"
          invalidateKeys={[['fund-metrics', schemeId], ['fund', schemeId]]}
        />
      </div>
      <section className="metrics compact-metrics snapshot-metrics fund-risk-metrics">
        <div className="metric">
          <small>Std deviation</small>
          <strong>{formatPct(metrics?.standard_deviation)}</strong>
        </div>
        <div className="metric">
          <small>Sharpe</small>
          <strong>{formatRatio(metrics?.sharpe)}</strong>
        </div>
        <div className="metric">
          <small>Sortino</small>
          <strong>{formatRatio(metrics?.sortino)}</strong>
        </div>
        <div className="metric">
          <small>Max drawdown</small>
          <strong>{formatPct(metrics?.maximum_drawdown)}</strong>
        </div>
        <div className="metric">
          <small>Alpha</small>
          <strong>{formatRatio(metrics?.alpha)}</strong>
        </div>
        <div className="metric">
          <small>Beta</small>
          <strong>{formatRatio(metrics?.beta)}</strong>
        </div>
      </section>
      <p className="panel-subtitle" style={{ marginTop: 12 }}>
        As of {metrics?.as_of_date || '—'}
        {metrics?.risk_free_rate != null ? ` · Rf ${formatPct(metrics.risk_free_rate)}` : ''}
        {metrics?.calculation_version != null ? ` · calc ${metrics.calculation_version}` : ''}
        {metrics?.available === false && metrics?.reason ? ` · ${metrics.reason}` : ''}
      </p>
    </section>
  );
}
