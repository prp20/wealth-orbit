import { describe, expect, it } from 'vitest';
import {
  failedSyncSummaries,
  formatSyncJobLabel,
  syncJobFailureMessage,
  syncQueueQuery,
} from '../api';
import { freshnessDateBits, freshnessFailureLine } from './syncFailures';

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

describe('freshnessFailureLine and dates', () => {
  it('surfaces failure while stale date bits remain available', () => {
    const freshness = {
      latest_price_date: '2026-11-01',
      latest_fundamental_period_end: '2026-03-31',
      last_sync_by_kind: {
        fundamentals: { status: 'FAILED', last_error: 'screener_html_unavailable' },
        prices: { status: 'SUCCEEDED', last_error: null },
      },
    };
    const dates = freshnessDateBits(freshness);
    const failure = freshnessFailureLine(freshness);
    expect(dates.join(' · ')).toContain('Price 1 Nov 2026');
    expect(dates.join(' · ')).toContain('Statements 31 Mar 2026');
    expect(failure).toContain('fundamentals failed: screener_html_unavailable');
    expect(failedSyncSummaries({ prices: { status: 'SUCCEEDED' } })).toEqual([]);
  });
});

describe('Recent sync jobs helpers', () => {
  it('builds include_history query params for the Home strip', () => {
    expect(syncQueueQuery(true, 8)).toBe('include_history=true&limit=8');
    expect(syncQueueQuery(false, 25)).toBe('include_history=false&limit=25');
  });

  it('labels entity and sync kind for the jobs list', () => {
    expect(
      formatSyncJobLabel({ entity_type: 'STOCK', entity_key: 'HDFCBANK', sync_type: 'FUNDAMENTALS' }),
    ).toBe('STOCK HDFCBANK · FUNDAMENTALS');
  });
});
