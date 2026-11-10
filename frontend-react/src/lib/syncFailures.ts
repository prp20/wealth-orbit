import { failedSyncSummaries, SyncJobByKind } from '../api';
import { formatDisplayDate } from './format';

export type FreshnessBits = {
  latest_price_date?: string | null;
  latest_fundamental_period_end?: string | null;
  latest_shareholding_period_end?: string | null;
  latest_technical_calculated_at?: string | null;
  latest_nav_date?: string | null;
  latest_metrics_as_of?: string | null;
  latest_enrichment_as_of?: string | null;
  last_sync_by_kind?: Record<string, SyncJobByKind | null | undefined>;
};

export function freshnessFailureLine(freshness: FreshnessBits | null | undefined): string | null {
  const failures = failedSyncSummaries(freshness?.last_sync_by_kind);
  if (!failures.length) return null;
  return failures.map((row) => `${row.kind} failed: ${row.reason}`).join(' · ');
}

/** Date chips shown beside failure lines so stale data stays visible. */
export function freshnessDateBits(freshness: FreshnessBits | null | undefined): string[] {
  if (!freshness) return [];
  return [
    freshness.latest_price_date ? `Price ${formatDisplayDate(freshness.latest_price_date)}` : null,
    freshness.latest_fundamental_period_end
      ? `Statements ${formatDisplayDate(freshness.latest_fundamental_period_end)}`
      : null,
    freshness.latest_shareholding_period_end
      ? `Shareholding ${formatDisplayDate(freshness.latest_shareholding_period_end)}`
      : null,
    freshness.latest_technical_calculated_at
      ? `Indicators ${formatDisplayDate(freshness.latest_technical_calculated_at)}`
      : null,
    freshness.latest_nav_date ? `NAV ${formatDisplayDate(freshness.latest_nav_date)}` : null,
    freshness.latest_metrics_as_of ? `Returns ${formatDisplayDate(freshness.latest_metrics_as_of)}` : null,
    freshness.latest_enrichment_as_of ? `Facts ${formatDisplayDate(freshness.latest_enrichment_as_of)}` : null,
  ].filter((bit): bit is string => Boolean(bit));
}
