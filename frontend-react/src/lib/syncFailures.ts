import { failedSyncSummaries, SyncJobByKind } from '../api';

export function freshnessFailureLine(
  freshness: { last_sync_by_kind?: Record<string, SyncJobByKind | null | undefined> } | null | undefined,
): string | null {
  const failures = failedSyncSummaries(freshness?.last_sync_by_kind);
  if (!failures.length) return null;
  return failures.map((row) => `${row.kind} failed: ${row.reason}`).join(' · ');
}
