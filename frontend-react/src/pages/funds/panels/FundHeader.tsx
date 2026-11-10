import SyncJobButton from '../../../components/SyncJobButton';
import { planOptionLabel } from '../../../lib/fundMetrics';
import { freshnessDateBits, freshnessFailureLine } from '../../../lib/syncFailures';

export default function FundHeader({ schemeId, fund }: { schemeId: string; fund: any }) {
  const freshness = fund?.freshness || {};
  const syncFailureLine = freshnessFailureLine(freshness);
  const subtitle = [
    fund?.amc_name,
    fund?.category_name,
    fund?.subcategory_name,
    planOptionLabel(fund?.plan_type),
    planOptionLabel(fund?.option_type),
  ].filter(Boolean).join(' · ');
  const dates = freshnessDateBits(freshness);

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
          extendHistory
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
      {syncFailureLine && <p className="panel-subtitle sync-failure-line">{syncFailureLine}</p>}
    </section>
  );
}
