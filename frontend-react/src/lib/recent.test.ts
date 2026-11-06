import { describe, expect, it } from 'vitest';
import { formatDisplayDate } from './format';
import { formatRecentWhen } from './recent';

describe('formatDisplayDate', () => {
  it('renders a calendar date without shifting the day', () => {
    expect(formatDisplayDate('2026-11-05')).toBe('5 Nov 2026');
    expect(formatDisplayDate('2026-11-05T18:30:00Z')).toBe('5 Nov 2026');
  });
});

describe('formatRecentWhen', () => {
  const now = new Date(2026, 10, 6, 15, 0, 0);

  it('uses today, yesterday, or the calendar date', () => {
    expect(formatRecentWhen(new Date(2026, 10, 6, 9, 0, 0).toISOString(), now)).toBe('Today');
    expect(formatRecentWhen(new Date(2026, 10, 5, 9, 0, 0).toISOString(), now)).toBe('Yesterday');
    expect(formatRecentWhen(new Date(2026, 9, 2, 9, 0, 0).toISOString(), now)).toBe('2 Oct 2026');
  });
});
