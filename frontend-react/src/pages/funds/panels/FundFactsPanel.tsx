import { useQuery } from '@tanstack/react-query';
import { api } from '../../../api';
import SyncJobButton from '../../../components/SyncJobButton';
import { formatCompactInr, formatDate, formatPct } from '../../../lib/format';

const FIELDS: { key: string; label: string; format?: (value: unknown) => string }[] = [
  { key: 'as_of_date', label: 'As of', format: formatDate },
  { key: 'fund_house', label: 'Fund house' },
  { key: 'fund_manager', label: 'Fund manager' },
  { key: 'scheme_category', label: 'Scheme category' },
  { key: 'scheme_start_date', label: 'Scheme start', format: formatDate },
  { key: 'aum', label: 'AUM', format: formatCompactInr },
  { key: 'expense_ratio', label: 'Expense ratio', format: formatPct },
  { key: 'exit_load', label: 'Exit load' },
];

export default function FundFactsPanel({ schemeId, fund }: { schemeId: string; fund: any }) {
  const enrichment = useQuery({
    queryKey: ['fund-enrichment', schemeId],
    queryFn: () => api.fundEnrichment(schemeId),
  });
  const latest =
    fund?.latest_enrichment ||
    (Array.isArray(enrichment.data) ? enrichment.data[0] : enrichment.data) ||
    null;

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Fund facts</h2>
          <p className="panel-subtitle">
            Identity from mftool/MFAPI; AUM, expense, manager, and exit load from Kuvera when matched.
          </p>
        </div>
        <SyncJobButton
          entity="fund"
          id={schemeId}
          kind="enrichment"
          invalidateKeys={[['fund-enrichment', schemeId], ['fund', schemeId]]}
        />
      </div>
      {enrichment.isLoading && !latest && <div className="loading">Loading fund facts…</div>}
      {enrichment.error && !latest && <div className="empty">{(enrichment.error as Error).message}</div>}
      {!latest && !enrichment.isLoading && (
        <div className="empty">No enrichment facts yet. Sync enrichment to populate this panel.</div>
      )}
      {latest && (
        <div className="detail-grid fund-facts-grid">
          {FIELDS.map((field) => {
            const raw = latest[field.key];
            const value = field.format ? field.format(raw) : raw == null || raw === '' ? '—' : String(raw);
            return (
              <div className="detail-item" key={field.key}>
                <small>{field.label}</small>
                <strong>{value}</strong>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
