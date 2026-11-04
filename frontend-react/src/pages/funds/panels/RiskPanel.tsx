import SyncJobButton from '../../../components/SyncJobButton';
import { formatDate, formatPct, formatRatio } from '../../../lib/format';

export default function RiskPanel({ schemeId, fund }: { schemeId: string; fund: any }) {
  const metrics = fund?.latest_metrics;
  const benchmark = fund?.benchmark;
  const observations = metrics?.observations;
  const aligned = metrics?.aligned_observations;
  const missingAligned =
    observations != null && aligned != null ? Math.max(0, Number(observations) - Number(aligned)) : null;

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Risk</h2>
          <p className="panel-subtitle">
            Daily NAV returns over the full available history (annualized with √252). Alpha/Beta require a
            mapped benchmark with aligned index history. Short periods (1M/3M/6M) store trailing return only
            and do not change these tiles.
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
        As of {formatDate(metrics?.as_of_date)}
        {benchmark?.available
          ? ` · Benchmark ${benchmark.index_name || benchmark.index_code}`
          : ' · Benchmark unmapped'}
        {metrics?.benchmark_as_of_date
          ? ` (bench as of ${formatDate(metrics.benchmark_as_of_date)})`
          : ''}
        {observations != null ? ` · Lookback ${observations} daily obs` : ''}
        {aligned != null ? ` · Aligned ${aligned}` : ''}
        {missingAligned != null && missingAligned > 0
          ? ` · Missing aligned days ${missingAligned} (dropped before alpha/beta)`
          : ''}
        {metrics?.risk_free_rate != null ? ` · Rf ${formatPct(metrics.risk_free_rate)}` : ''}
        {metrics?.calculation_version != null ? ` · calc ${metrics.calculation_version}` : ''}
        {metrics?.available === false && metrics?.reason ? ` · ${metrics.reason}` : ''}
      </p>
    </section>
  );
}
