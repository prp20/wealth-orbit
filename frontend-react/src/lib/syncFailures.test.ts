import { describe, expect, it } from 'vitest';
import { failedSyncSummaries, syncJobFailureMessage } from '../api';
import { freshnessFailureLine } from './syncFailures';

describe('syncJobFailureMessage', () => {
  it('returns last_error for FAILED jobs', () => {
    expect(syncJobFailureMessage({ status: 'FAILED', last_error: 'yahoo_empty_info' })).toBe(
      'yahoo_empty_info',
    );
  });

  it('does not treat zero-row SUCCEEDED results as failures', () => {
    expect(
      syncJobFailureMessage({
        status: 'SUCCEEDED',
        result: { fundamental_rows: 0, shareholding_rows: 0, status: 'completed' },
      }),
    ).toBeNull();
  });
});

describe('freshnessFailureLine', () => {
  it('keeps stale dates separate and surfaces failed kinds', () => {
    const line = freshnessFailureLine({
      last_sync_by_kind: {
        fundamentals: { status: 'FAILED', last_error: 'screener_html_unavailable' },
        prices: { status: 'SUCCEEDED', last_error: null },
      },
    });
    expect(line).toContain('fundamentals failed: screener_html_unavailable');
    expect(failedSyncSummaries({ prices: { status: 'SUCCEEDED' } })).toEqual([]);
  });
});
