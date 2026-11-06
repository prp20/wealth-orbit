import SyncJobButton from '../../../components/SyncJobButton';
import { formatDisplayDate } from '../../../lib/format';
import { planOptionLabel } from '../../../lib/fundMetrics';

export default function FundHeader({ schemeId, fund }: { schemeId: string; fund: any }) {
  const freshness = fund?.freshness || {};
  const subtitle = [
    fund?.amc_name,
    fund?.category_name,
    fund?.subcategory_name,
    planOptionLabel(fund?.plan_type),
    planOptionLabel(fund?.option_type),
  ].filter(Boolean).join(' · ');
  const dates = [
    freshness.latest_nav_date ? `NAV ${formatDisplayDate(freshness.latest_nav_date)}` : '',
    freshness.latest_metrics_as_of ? `Returns ${formatDisplayDate(freshness.latest_metrics_as_of)}` : '',
    freshness.latest_enrichment_as_of ? `Facts ${formatDisplayDate(freshness.latest_enrichment_as_of)}` : '',
  ].filter(Boolean);

  return (
    <section className="stock-header panel">
      <div className="stock-header-main">
        <div>
          <p className="eyebrow">{fund?.scheme_code || '—'}</p>
          <h1 className="stock-title">{fund?.scheme_name || fund?.scheme_code || 'Fund'}</h1>
          <p className="subtitle">{subtitle || '—'}</p>
        </div>
        <SyncJobButton
          entity="fund"
          id={schemeId}
          kind="nav"
          thenKind="metrics"
          label="Update returns"
          hideSucceeded
          invalidateKeys={[
            ['fund', schemeId],
            ['fund-metrics', schemeId],
            ['history', 'fund', schemeId],
            ['fund-similar', schemeId],
          ]}
        />
      </div>
      <p className="panel-subtitle fund-freshness">
        {dates.length ? dates.join(' · ') : 'No NAV, returns, or facts loaded yet.'}
      </p>
    </section>
  );
}
