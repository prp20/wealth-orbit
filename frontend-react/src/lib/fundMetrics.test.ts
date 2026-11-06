import { describe, expect, it } from 'vitest';
import { periodReturnLabel, periodReturnValue, planOptionLabel } from './fundMetrics';

describe('period return wording', () => {
  it('names a short or one-year change as a return and longer periods as CAGR', () => {
    expect(periodReturnLabel('1M')).toBe('1-month return');
    expect(periodReturnLabel('1Y')).toBe('1-year return');
    expect(periodReturnLabel('3Y')).toBe('3-year CAGR');
    expect(periodReturnLabel('10Y')).toBe('10-year CAGR');
  });

  it('reads trailing return for one year and CAGR for three years', () => {
    expect(periodReturnValue({ metric_period: '1Y', trailing_return: 0.12, cagr: 0.11 })).toBe(0.12);
    expect(periodReturnValue({ metric_period: '3Y', trailing_return: 0.4, cagr: 0.13 })).toBe(0.13);
  });
});

describe('planOptionLabel', () => {
  it('uses the research words for stored plan and option codes', () => {
    expect(planOptionLabel('DIRECT')).toBe('Direct');
    expect(planOptionLabel('GROWTH')).toBe('Growth');
    expect(planOptionLabel('IDCW')).toBe('IDCW');
    expect(planOptionLabel('PAYOUT')).toBe('Payout');
  });
});